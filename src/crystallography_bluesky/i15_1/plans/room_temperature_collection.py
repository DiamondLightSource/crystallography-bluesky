from functools import partial
from math import ceil
from typing import Any

import bluesky.plan_stubs as bps
from bluesky.utils import MsgGenerator
from daq_config_server.models.i15_1.positions_to_times import AnglesToTimes
from dodal.common import inject
from dodal.common.beamlines.beamline_utils import get_config_client
from dodal.devices.motors import Motor
from dodal.log import LOGGER
from ophyd_async.core import SignalRW, StandardReadable

from crystallography_bluesky.i15_1.plans.generic_collection import (
    GenericCollectionDevices,
    setup_and_teardown_collection,
)
from crystallography_bluesky.i15_1.plans.setup_zebra import (
    setup_zebra_for_software_triggering,
)

TTH_ANGLE_TO_COLLECTION_TIME_FILEPATH = (
    "/dls_sw/i15-1/software/daq_configuration/tth_angle_to_collection_time.txt"
)

devices = inject("")


def _calculate_number_of_frames(
    fraction_of_time: float,
    full_collection_time: float,
    exposure_time_per_frame: float,
) -> int:
    return ceil((fraction_of_time * full_collection_time) / exposure_time_per_frame)


def calculate_frames_per_angle(
    full_collection_time: float, exposure_time_per_frame: float
):
    config_client = get_config_client()
    positions_to_fraction = config_client.get_file_contents(
        TTH_ANGLE_TO_COLLECTION_TIME_FILEPATH,
        AnglesToTimes,
    ).tth_angle_to_collection_time

    frames_per_angle = {}
    total_frames = 0
    for angle, fraction in positions_to_fraction.items():
        frames = _calculate_number_of_frames(
            fraction, full_collection_time, exposure_time_per_frame
        )
        frames_per_angle[angle] = frames
        total_frames += frames

    LOGGER.info(
        f"Total exposure time will be {total_frames * exposure_time_per_frame} compared"
        f" to user specified {full_collection_time}"
    )
    return frames_per_angle, total_frames


def inner_collection(
    tth: Motor,
    detector_trigger: SignalRW,
    frames_per_angle: dict[float, int],
    exposure_time_per_frame: float,
    signals_to_read_per_point: list[StandardReadable] | None = None,
):
    if not signals_to_read_per_point:
        signals_to_read_per_point = []
    signals_to_read_per_point.append(tth)
    for position, frames in frames_per_angle.items():
        yield from bps.mv(tth, position)
        current_tth = yield from bps.rd(tth)
        LOGGER.info(f"Triggering i0 and eiger {frames} times at tth of {current_tth}")
        for _ in range(int(frames)):
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

    async def calc_timeout(*_, **__):
        return 60

    # tth is currently very slow, speed will be improved for run
    generic_collection_devices.tth.movable_logic.calculate_timeout = calc_timeout

    yield from setup_zebra_for_software_triggering(generic_collection_devices.zebra)

    frames_per_angle, total_frames = calculate_frames_per_angle(
        full_collection_time, exposure_time_per_frame
    )

    detector_trigger = generic_collection_devices.zebra.inputs.soft_in_1
    tth = generic_collection_devices.tth

    collection = partial(
        inner_collection,
        tth,
        detector_trigger,
        frames_per_angle,
        exposure_time_per_frame,
    )

    yield from setup_and_teardown_collection(
        total_frames,
        exposure_time_per_frame,
        generic_collection_devices,
        collection,
        [
            generic_collection_devices.robot.spinner,
            generic_collection_devices.xtal,
            generic_collection_devices.attenuator,
        ]
        + (baseline_devices or []),
        metadata=metadata,
    )
