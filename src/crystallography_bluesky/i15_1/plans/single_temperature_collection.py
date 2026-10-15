import json
import time
from functools import partial
from math import ceil
from typing import Any, Literal, Self, TypeAlias

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
from dodal.devices.zebra.zebra import ArmDemand, Zebra
from dodal.devices.zebra.zebra_controlled_shutter import OpenClose, ZebraFastShutter
from dodal.log import LOGGER
from ophyd_async.core import StandardReadable, wait_for_value
from pydantic import BaseModel, model_validator

from crystallography_bluesky.i15_1.plans.generic_collection import (
    AuxiliaryScanType,
    DataCollectionScanType,
    GenericCollectionDevices,
    get_default_baseline_devices,
    setup_and_teardown_collection,
)
from crystallography_bluesky.i15_1.plans.setup_zebra import (
    setup_zebra_for_hardware_triggering,
    update_zebra_hardware_triggering,
)


class CollectionSpecPerPosition(BaseModel):
    # The structure of this is put in the nexus file and subsequently
    # used by analysis. If we change it we need to change it there too
    tth: float
    frames: int
    slow_attenuator_position: SlowAttenuatorPositions
    fast_attenuator: FastAttenuatorDemand


CollectionSpecification: TypeAlias = list[CollectionSpecPerPosition]


class CollectionSpecPerTemp(BaseModel):
    # The structure of this is put in the nexus file and subsequently
    # used by analysis. If we change it we need to change it there too
    temperature_celsius: float | Literal["RT"]
    temperature_unit: Literal["C", "K"] | None
    collection_specification: CollectionSpecification

    @model_validator(mode="after")
    def temperature_must_have_units(self) -> Self:
        if isinstance(self.temperature_celsius, float):
            assert self.temperature_unit is not None, (
                "Must provide a temperature unit if a temperature is given"
            )
        return self

    @model_validator(mode="after")
    def no_temperature_must_not_have_units(self) -> Self:
        if self.temperature_celsius == "RT":
            assert self.temperature_unit is None, (
                "Must not provide a temperature unit if no temperature float is given"
            )
        return self


TemperatureCollectionSpecification: TypeAlias = list[CollectionSpecPerTemp]

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
        reset_cached_result=True,
    ).tth_angle_to_specification

    collection_spec: CollectionSpecification = []
    total_frames = 0
    for angle, spec in collection_spec_from_config.items():
        frames = _calculate_number_of_frames(
            spec.exposure_time, full_collection_time, exposure_time_per_frame
        )
        collection_spec.append(
            CollectionSpecPerPosition(
                tth=angle,
                frames=frames,
                slow_attenuator_position=SlowAttenuatorPositions.from_trans_float(
                    spec.slow_attenuator_transmission
                ),
                fast_attenuator=FastAttenuatorDemand[spec.fast_attenuator_position],
            )
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
    fast_shutter: ZebraFastShutter,
    slow_attenuator: SlowAttenuator,
    fast_attenuator: FastAttenuator,
    collection_spec: CollectionSpecification,
    time_between_frames: float,
    signals_to_read_per_point: list[StandardReadable] | None = None,
):
    if not signals_to_read_per_point:
        signals_to_read_per_point = []
    if tth not in signals_to_read_per_point:
        signals_to_read_per_point.append(tth)
    for point_spec in collection_spec:
        yield from bps.mv(fast_shutter, OpenClose.CLOSE)
        yield from bps.mv(
            tth,
            point_spec.tth,
            slow_attenuator,
            point_spec.slow_attenuator_position,
            fast_attenuator,
            point_spec.fast_attenuator,
        )
        yield from bps.mv(fast_shutter, OpenClose.OPEN)
        current_tth = yield from bps.rd(tth)
        LOGGER.info(
            f"Triggering i0 and eiger {point_spec.frames} times at tth of {current_tth}"
            f", attenuation of {point_spec.slow_attenuator_position} and "
            f"fast attenuator {point_spec.fast_attenuator}"
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
        t0 = time.monotonic()
        # Collected signals at roughly the same time as the frames, by dead reckoning
        for i in range(int(point_spec.frames)):
            yield from bps.create(name="data")
            for signal in signals_to_read_per_point:
                yield from bps.read(signal)
            yield from bps.save()

            time_taken = time.monotonic() - t0
            next_hardware_trigger_time = (i + 1) * time_between_frames
            if (diff := (next_hardware_trigger_time - time_taken)) >= 0:
                yield from bps.sleep(diff)
            else:
                LOGGER.warning(
                    "Signal reading is behind hardware triggering of the detectors by "
                    + f"{-diff} seconds. Choose a longer exposure time per frame to "
                    + f"better correlate {signals_to_read_per_point} readings with "
                    + "detector frames."
                )

        LOGGER.info(
            f"Collected {point_spec.frames} signals at tth of {current_tth}"
            f" by dead reckoning"
        )

        # Sleeping after each frame to align with hardware triggers should result in the
        # overall trigger sequence having finished as or before we get here, but on the
        # off-chance that it hasn't, explicitly wait for the zebra Arm Status signal to
        # go to disarmed.
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
    scan_type: DataCollectionScanType | AuxiliaryScanType,
    generic_collection_devices: GenericCollectionDevices = devices,
    baseline_devices: list[StandardReadable] | None = None,
    metadata: dict[str, Any] | None = None,
) -> MsgGenerator:

    minimum_dead_time = 0.0001  # Minimum value independent of timebase
    trigger_pulse_width = 0.0001  # Assumes zebra is set to seconds timebase

    collection_spec, total_frames = get_collection_specification(
        full_collection_time, exposure_time_per_frame
    )

    first_frames_value = next(iter(collection_spec)).frames
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
        generic_collection_devices.fast_shutter,
        generic_collection_devices.slow_attenuator,
        generic_collection_devices.fast_attenuator,
        collection_spec,
        time_between_frames,
        signals_to_read_per_point=[generic_collection_devices.synchrotron],
    )

    all_baseline_devices = get_default_baseline_devices(generic_collection_devices) + (
        baseline_devices or []
    )

    # We're using the tth in the scan so do not want to take the baseline reading
    all_baseline_devices.remove(tth)

    metadata = metadata or {}
    metadata.update(
        {  # Need to serialise because nexus writer can't handle lists
            "collection_specification": json.dumps(
                [
                    CollectionSpecPerTemp(
                        temperature_celsius="RT",
                        temperature_unit=None,
                        collection_specification=collection_spec,
                    ).model_dump()
                ]
            )
        }
    )
    yield from setup_and_teardown_collection(
        total_frames,
        exposure_time_per_frame,
        generic_collection_devices,
        collection,
        scan_type,
        all_baseline_devices,
        metadata=metadata,
    )
