from dataclasses import dataclass
from functools import partial
from math import ceil
from typing import Any, TypeAlias

import bluesky.plan_stubs as bps
from bluesky.utils import MsgGenerator
from daq_config_server.models.i15_1.collection_specification import (
    CollectionSpecification as CollectionSpecFromConfig,
)
from dodal.common import inject
from dodal.common.beamlines.beamline_utils import get_config_client
from dodal.devices.beamlines.i15_1.attenuator import Attenuator, AttenuatorPositions
from dodal.devices.motors import Motor
from dodal.devices.zebra.zebra import ArmDemand, Zebra
from dodal.log import LOGGER
from ophyd_async.core import StandardReadable, wait_for_value

from crystallography_bluesky.i15_1.plans.generic_collection import (
    GenericCollectionDevices,
    get_default_baseline_devices,
    setup_and_teardown_collection,
)
from crystallography_bluesky.i15_1.plans.setup_zebra import (
    setup_zebra_for_hardware_triggering,
    update_zebra_hardware_triggering,
)


@dataclass
class SpecificationPerPosition:
    frames: int
    transmission: AttenuatorPositions


CollectionSpecification: TypeAlias = dict[float, SpecificationPerPosition]


COLLECTION_SPEC_FILEPATH = (
    "/dls_sw/i15-1/software/daq_configuration/collection_specification.txt"
)

devices = inject("")


def _calculate_number_of_frames(
    fraction_of_time: float,
    full_collection_time: float,
    exposure_time_per_frame: float,
) -> int:
    return ceil((fraction_of_time * full_collection_time) / exposure_time_per_frame)


def get_collection_specification(
    full_collection_time: float, exposure_time_per_frame: float
) -> tuple[CollectionSpecification, int]:
    """The standard collection specification is defined in configuration but needs
    conversion:
     * The config specifies exposure in percentage of total time, we want number of
       frames.
     * The transmission is just a float, we want to convert to one of the aperture
       options.
    """
    config_client = get_config_client()
    collection_spec_from_config = config_client.get_file_contents(
        COLLECTION_SPEC_FILEPATH,
        CollectionSpecFromConfig,
    ).tth_angle_to_specification

    collection_spec: CollectionSpecification = {}
    total_frames = 0
    for angle, spec in collection_spec_from_config.items():
        frames = _calculate_number_of_frames(
            spec.exposure_time, full_collection_time, exposure_time_per_frame
        )
        collection_spec[angle] = SpecificationPerPosition(
            frames, AttenuatorPositions.from_trans_float(spec.transmission)
        )
        total_frames += frames

    LOGGER.info(
        f"Total exposure time will be {total_frames * exposure_time_per_frame} compared"
        f" to user specified {full_collection_time}"
    )
    return collection_spec, total_frames


def inner_collection(
    tth: Motor,
    zebra: Zebra,
    attenuator: Attenuator,
    collection_spec: CollectionSpecification,
    time_between_frames: float,
    signals_to_read_per_point: list[StandardReadable] | None = None,
):
    if not signals_to_read_per_point:
        signals_to_read_per_point = []
    signals_to_read_per_point.append(tth)
    for position, point_spec in collection_spec.items():
        yield from bps.mv(tth, position, attenuator, point_spec.transmission)
        current_tth = yield from bps.rd(tth)
        LOGGER.info(
            f"Triggering i0 and eiger {point_spec.frames} times at tth of {current_tth}"
            f" and attenuation of {point_spec.transmission}"
        )

        # Set number of frame for this position
        yield from update_zebra_hardware_triggering(
            zebra,
            point_spec.frames,
            time_between_frames,
        )
        yield from bps.wait()

        # Arm zebra
        yield from bps.abs_set(zebra.pc.arm, ArmDemand.ARM, wait=True)
        # Here wait=True means this waits for the arm to be started, not
        # for the collection to complete. Log time so we can verify:
        LOGGER.info(
            f"Triggered i0 and eiger {point_spec.frames} times at tth of {current_tth}"
        )

        # Collected signals at roughly the same time as the frames, by dead reckoning
        for _ in range(int(point_spec.frames)):
            yield from bps.create(name="data")
            for signal in signals_to_read_per_point:
                yield from bps.read(signal)
            yield from bps.save()
            yield from bps.sleep(time_between_frames)

        LOGGER.info(
            f"Collected {point_spec.frames} signals at tth of {current_tth}"
            f" by dead reckoning"
        )

        # Sleeping for time_between_frames for each iteration of the loop
        # above should result in the overall trigger sequence having finished
        # as or before we get here, but on the off-chance that it hasn't,
        # explicitly wait for the zebra Arm Status signal to go to disarmed.
        yield from bps.wait_for(
            [lambda: wait_for_value(zebra.pc.arm.armed, 0, timeout=5.0)]
        )

        # This avoids continuing on to the next tth before the zebra has completed
        # triggering the current position if the timing is slightly off.
        # Log time so we can verify now too:
        LOGGER.info(f"Completed {point_spec.frames} triggers at tth of {current_tth}")


def data_collection(
    full_collection_time: float,
    exposure_time_per_frame: float,
    generic_collection_devices: GenericCollectionDevices = devices,
    baseline_devices: list[StandardReadable] | None = None,
    metadata: dict[str, Any] | None = None,
) -> MsgGenerator:

    minimum_dead_time = 0.0001  # Minimum value independent of timebase
    trigger_pulse_width = 0.0001  # Assumes zebra is set to seconds timebase

    collection_spec, total_frames = get_collection_specification(
        full_collection_time, exposure_time_per_frame
    )

    first_frames_value = next(iter(collection_spec.values())).frames
    time_between_frames = exposure_time_per_frame + minimum_dead_time

    yield from setup_zebra_for_hardware_triggering(
        generic_collection_devices.zebra,
        first_frames_value,
        time_between_frames,
        trigger_pulse_width,
    )

    tth = generic_collection_devices.tth

    collection = partial(
        inner_collection,
        tth,
        generic_collection_devices.zebra,
        generic_collection_devices.attenuator,
        collection_spec,
        time_between_frames,
    )

    all_baseline_devices = get_default_baseline_devices(generic_collection_devices) + (
        baseline_devices or []
    )

    # We're using the tth in the scan so do not want to take the baseline reading
    all_baseline_devices.remove(tth)

    metadata = metadata or {}
    metadata.update(
        {
            "data_shape": [(total_frames, "collection")],
            "variables": {},
            "collection_specification": collection_spec,
        }
    )
    yield from setup_and_teardown_collection(
        total_frames,
        exposure_time_per_frame,
        generic_collection_devices,
        collection,
        all_baseline_devices,
        metadata=metadata,
    )
