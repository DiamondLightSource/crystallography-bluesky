import bluesky.plan_stubs as bps
from bluesky.utils import MsgGenerator
from dodal.common import inject
from dodal.log import LOGGER
from ophyd_async.core import StandardReadable
from ophyd_async.epics.motor import Motor

from crystallography_bluesky.i15_1.plans.generic_collection import (
    GenericCollectionDevices,
    generic_collection,
)

devices = inject("")

positions_to_percentage: dict[float, float] = {
    10: 0.05,
    20: 0.05,
    30: 0.1,
    40: 0.2,
    50: 0.3,
    60: 0.3,
}  # Need to asser adds to <= 1


def data_collection(
    full_collection_time: float,
    exposure_time_per_frame: float,
    generic_collection_devices: GenericCollectionDevices = devices,
    baseline_devices: list[StandardReadable] | None = None,
) -> MsgGenerator:

    async def calc_timeout(*_, **__):
        return 60

    generic_collection_devices.tth.movable_logic.calculate_timeout = calc_timeout

    def collection():
        for position, percentage in positions_to_percentage.items():
            tth = generic_collection_devices.tth
            yield from bps.mv(tth, position)
            current_tth = yield from bps.rd(tth)
            LOGGER.info(f"Theta at {current_tth}")
            frames = (
                percentage * full_collection_time
            ) // exposure_time_per_frame  # Need to assert always > 0
            LOGGER.info(f"Triggering i0 and eiger {frames} times")
            for _ in range(int(frames)):
                yield from bps.create(name="tth")
                yield from bps.read(tth)
                yield from bps.save()
                yield from bps.abs_set(
                    generic_collection_devices.zebra.inputs.soft_in_1, 1, wait=True
                )
                yield from bps.sleep(exposure_time_per_frame)
                yield from bps.abs_set(
                    generic_collection_devices.zebra.inputs.soft_in_1, 0, wait=True
                )

    total_frames = 0
    for _, percentage in positions_to_percentage.items():
        total_frames += (
            percentage * full_collection_time
        ) // exposure_time_per_frame  # Need to assert always > 0

    yield from generic_collection(
        int(total_frames),
        exposure_time_per_frame,
        lambda: None,
        generic_collection_devices,
        collection,
        baseline_devices,
    )
