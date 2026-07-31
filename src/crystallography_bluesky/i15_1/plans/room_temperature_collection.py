from math import ceil

import bluesky.plan_stubs as bps
from bluesky.utils import MsgGenerator
from dodal.common import inject
from dodal.log import LOGGER
from ophyd_async.core import StandardReadable

from crystallography_bluesky.i15_1.plans.generic_collection import (
    GenericCollectionDevices,
    setup_and_teardown_collection,
)

devices = inject("")

# See https://github.com/DiamondLightSource/crystallography-bluesky/issues/111 for a
# cleaner solution to this
positions_to_fraction: dict[float, float] = {
    10: 0.05,
    20: 0.05,
    30: 0.1,
    40: 0.2,
    50: 0.3,
    60: 0.3,
}


def _calculate_number_of_frames(
    fraction_of_time: float,
    full_collection_time: float,
    exposure_time_per_frame: float,
) -> int:
    return ceil((fraction_of_time * full_collection_time) / exposure_time_per_frame)


def data_collection(
    full_collection_time: float,
    exposure_time_per_frame: float,
    generic_collection_devices: GenericCollectionDevices = devices,
    baseline_devices: list[StandardReadable] | None = None,
) -> MsgGenerator:

    async def calc_timeout(*_, **__):
        return 60

    # tth is currently very slow, speed will be improved for run
    generic_collection_devices.tth.movable_logic.calculate_timeout = calc_timeout

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

    def collection():
        for position, frames in frames_per_angle.items():
            tth = generic_collection_devices.tth
            yield from bps.mv(tth, position)
            current_tth = yield from bps.rd(tth)
            LOGGER.info(
                f"Triggering i0 and eiger {frames} times at tth of {current_tth}"
            )
            detector_trigger = generic_collection_devices.zebra.inputs.soft_in_1
            for _ in range(int(frames)):
                yield from bps.create(name="tth")
                yield from bps.read(tth)
                yield from bps.save()
                yield from bps.abs_set(detector_trigger, 1, wait=True)
                yield from bps.sleep(exposure_time_per_frame)
                yield from bps.abs_set(detector_trigger, 0, wait=True)

    yield from setup_and_teardown_collection(
        int(total_frames),
        exposure_time_per_frame,
        generic_collection_devices,
        collection,
        [generic_collection_devices.robot.spinner, generic_collection_devices.xtal]
        + (baseline_devices or []),
    )
