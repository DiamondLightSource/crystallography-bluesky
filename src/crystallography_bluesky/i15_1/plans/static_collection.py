from typing import Any

import bluesky.plan_stubs as bps
from bluesky.utils import MsgGenerator
from dodal.common import inject
from dodal.devices.beamlines.i15_1.attenuator import AttenuatorPositions
from dodal.devices.zebra.zebra import ArmDemand
from ophyd_async.core import StandardReadable

from crystallography_bluesky.i15_1.plans.generic_collection import (
    GenericCollectionDevices,
    get_default_baseline_devices,
    setup_and_teardown_collection,
)
from crystallography_bluesky.i15_1.plans.setup_zebra import (
    setup_zebra_for_hardware_triggering,
)

devices = inject("")


def static_collection(
    frames: int,
    exposure_time: float,
    attenuation: AttenuatorPositions,
    time_between_frames: float = 0.1,
    devices: GenericCollectionDevices = devices,
    baseline_devices: list[StandardReadable] | None = None,
    metadata: dict[str, Any] | None = None,
) -> MsgGenerator:
    """Take a hardware-triggered static collection with the eiger and i0 detectors.

    Args:
        frames (int): Number of frames to capture
        exposure_time (float): Exposure time of each frame
        attenuation (AttenuatorPositions): The attenuation to run the collection with
        time_between_frames (float): The time between each frame
        devices (GenericCollectionDevices, optional): The standard devices needed for
                the collection.
        baseline_devices (list[StandardReadable] | None, optional): Any other devices to
                record metadata from. Defaults to None.
    """
    DEFAULT_BASELINE_DEVICES = get_default_baseline_devices(devices)

    yield from bps.mv(devices.attenuator, attenuation)

    yield from setup_zebra_for_hardware_triggering(
        devices.zebra, frames, time_between_frames
    )

    def collection():
        yield from bps.abs_set(devices.zebra.pc.arm, ArmDemand.ARM, wait=True)
        yield from bps.sleep(frames * time_between_frames)

    yield from setup_and_teardown_collection(
        frames=frames,
        exposure_time=exposure_time,
        devices=devices,
        collection=collection,
        baseline_devices=DEFAULT_BASELINE_DEVICES + (baseline_devices or []),
        metadata=metadata,
    )
