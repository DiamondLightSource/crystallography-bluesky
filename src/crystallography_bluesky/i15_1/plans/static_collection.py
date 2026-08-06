from functools import partial
from typing import Any

from bluesky.utils import MsgGenerator
from dodal.common import inject
from ophyd_async.core import StandardReadable

from crystallography_bluesky.i15_1.plans.generic_collection import (
    TIME_BETWEEN_FRAMES,
    GenericCollectionDevices,
    hardware_triggered_collection,
    setup_and_teardown_collection,
)

devices = inject("")


def static_collection(
    frames: int,
    exposure_time: float,
    time_between_frames: float = 0.1,
    devices: GenericCollectionDevices = devices,
    baseline_devices: list[StandardReadable] | None = None,
    metadata: dict[str, Any] | None = None,
) -> MsgGenerator:
    """Take a hardware-triggered static collection with the eiger and i0 detectors.

    Args:
        frames (int): Number of frames to capture
        exposure_time (float): Exposure time of each frame
        time_between_frames (float): The time between each frame
        devices (GenericCollectionDevices, optional): The standard devices needed for
                the collection.
        baseline_devices (list[StandardReadable] | None, optional): Any other devices to
                record metadata from. Defaults to None.
    """
    DEFAULT_BASELINE_DEVICES = [devices.robot.spinner, devices.xtal, devices.tth]
    collection = partial(
        hardware_triggered_collection,
        zebra=devices.zebra,
        frames=frames,
        time_between_frames=TIME_BETWEEN_FRAMES,
    )
    yield from setup_and_teardown_collection(
        frames=frames,
        exposure_time=exposure_time,
        devices=devices,
        collection=collection,
        baseline_devices=DEFAULT_BASELINE_DEVICES + (baseline_devices or []),
        metadata=metadata,
    )
