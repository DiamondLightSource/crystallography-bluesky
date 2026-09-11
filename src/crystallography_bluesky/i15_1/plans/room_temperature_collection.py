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
from dodal.devices.beamlines.i15_1.attenuators import (
    FastAttenuator,
    FastAttenuatorDemand,
    SlowAttenuator,
    SlowAttenuatorPositions,
)
from dodal.devices.motors import Motor
from dodal.log import LOGGER
from ophyd_async.core import SignalRW, StandardReadable

from crystallography_bluesky.i15_1.plans.generic_collection import (
    GenericCollectionDevices,
    get_default_baseline_devices,
    setup_and_teardown_collection,
)
from crystallography_bluesky.i15_1.plans.setup_zebra import (
    setup_zebra_for_software_triggering,
)


@dataclass
class SpecificationPerPosition:
    frames: int
    slow_attenuator_position: SlowAttenuatorPositions
    fast_attenuator: FastAttenuatorDemand


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
            frames,
            SlowAttenuatorPositions.from_trans_float(spec.slow_attenuator_transmission),
            FastAttenuatorDemand[spec.fast_attenuator_position],
        )
        total_frames += frames

    LOGGER.info(
        f"Total exposure time will be {total_frames * exposure_time_per_frame} compared"
        f" to user specified {full_collection_time}"
    )
    return collection_spec, total_frames


def inner_collection(
    tth: Motor,
    detector_trigger: SignalRW,
    slow_attenuator: SlowAttenuator,
    fast_attenuator: FastAttenuator,
    collection_spec: CollectionSpecification,
    exposure_time_per_frame: float,
    signals_to_read_per_point: list[StandardReadable] | None = None,
):
    if not signals_to_read_per_point:
        signals_to_read_per_point = []
    signals_to_read_per_point.append(tth)
    for position, point_spec in collection_spec.items():
        yield from bps.mv(
            tth,
            position,
            slow_attenuator,
            point_spec.slow_attenuator_position,
            fast_attenuator,
            point_spec.fast_attenuator,
        )
        current_tth = yield from bps.rd(tth)
        LOGGER.info(
            f"Triggering i0 and eiger {point_spec.frames} times at tth of {current_tth}"
            f", attenuation of {point_spec.slow_attenuator_position} and "
            f"fast attenuator {point_spec.fast_attenuator}"
        )
        for _ in range(int(point_spec.frames)):
            yield from bps.create(name="data")
            for signal in signals_to_read_per_point:
                yield from bps.read(signal)
            yield from bps.save()
            yield from bps.abs_set(detector_trigger, 1, wait=True)
            yield from bps.sleep(exposure_time_per_frame)
            yield from bps.abs_set(detector_trigger, 0, wait=True)


def data_collection(
    full_collection_time: float,
    exposure_time_per_frame: float,
    generic_collection_devices: GenericCollectionDevices = devices,
    baseline_devices: list[StandardReadable] | None = None,
    metadata: dict[str, Any] | None = None,
) -> MsgGenerator:

    yield from setup_zebra_for_software_triggering(generic_collection_devices.zebra)

    collection_spec, total_frames = get_collection_specification(
        full_collection_time, exposure_time_per_frame
    )

    detector_trigger = generic_collection_devices.zebra.inputs.soft_in_1
    tth = generic_collection_devices.tth

    collection = partial(
        inner_collection,
        tth,
        detector_trigger,
        generic_collection_devices.slow_attenuator,
        generic_collection_devices.fast_attenuator,
        collection_spec,
        exposure_time_per_frame,
    )

    all_baseline_devices = get_default_baseline_devices(generic_collection_devices) + (
        baseline_devices or []
    )

    # We're using the tth in the scan so do not want to take the baseline reading
    all_baseline_devices.remove(tth)

    yield from setup_and_teardown_collection(
        total_frames,
        exposure_time_per_frame,
        generic_collection_devices,
        collection,
        all_baseline_devices,
        metadata=metadata,
    )
