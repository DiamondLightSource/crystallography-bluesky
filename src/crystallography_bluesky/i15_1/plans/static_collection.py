import bluesky.plan_stubs as bps
from bluesky.utils import MsgGenerator
from dodal.common import inject
from ophyd_async.core import StandardReadable

from crystallography_bluesky.i15_1.plans.generic_collection import (
    GenericCollectionDevices,
    generic_collection,
)

devices = inject("")


def static_collection(
    frames: int,
    exposure_time: float,
    time_between_frames: float = 0.1,
    devices: GenericCollectionDevices = devices,
    baseline_devices: list[StandardReadable] | None = None,
) -> MsgGenerator:
    """Take a static collection with the eiger and i0 detectors.

    Args:
        frames (int): Number of frames to capture
        exposure_time (float): Exposure time of each frame
        time_between_frames (float): The time between each frame
        devices (GenericCollectionDevices, optional): The standard devices needed for
                the collection.
        baseline_devices (list[StandardReadable] | None, optional): Any other devices to
                record metadata from. Defaults to None.
    """
    yield from generic_collection(
        frames,
        exposure_time,
        lambda: bps.sleep(time_between_frames - exposure_time),
        devices,
        baseline_devices,
    )
