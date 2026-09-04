from collections.abc import Callable
from typing import Any

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
import pydantic
from bluesky.utils import MsgGenerator
from dodal.common import inject
from dodal.devices.beamlines.i15_1.attenuator import Attenuator
from dodal.devices.beamlines.i15_1.laue import LaueMonochrometer
from dodal.devices.beamlines.i15_1.robot import Robot
from dodal.devices.tetramm import SummingTetrammDetector
from dodal.devices.zebra.zebra import Zebra
from dodal.devices.zebra.zebra_controlled_shutter import OpenClose, ZebraFastShutter
from dodal.log import LOGGER
from ophyd_async.core import DetectorTrigger, StandardReadable, TriggerInfo
from ophyd_async.epics.motor import Motor
from ophyd_async.fastcs.eiger import EigerDetector

from crystallography_bluesky.i15_1.plans.setup_zebra import (
    setup_zebra_for_software_triggering,
)

devices = inject("")


@pydantic.dataclasses.dataclass(config={"arbitrary_types_allowed": True})
class GenericCollectionDevices:
    fastcs_eiger: EigerDetector
    i0: SummingTetrammDetector
    zebra: Zebra
    robot: Robot
    tth: Motor
    fast_shutter: ZebraFastShutter
    xtal: LaueMonochrometer
    attenuator: Attenuator


def get_default_baseline_devices(all_devices: GenericCollectionDevices):
    return [
        all_devices.robot.spinner,
        all_devices.xtal,
        all_devices.tth,
        all_devices.attenuator,
    ]


def setup_and_teardown_collection(
    frames: int,
    exposure_time: float,
    devices: GenericCollectionDevices,
    collection: Callable[[], MsgGenerator],
    baseline_devices: list[StandardReadable] | None = None,
    metadata: dict[str, Any] | None = None,
) -> MsgGenerator:
    """Setup and tear down the eiger and i0 detectors for a collection. The specific
    collection performed (including triggering the detectors through the zebra) should
    be specified in the provided `collection`.

    Args:
        frames (int): Number of frames to capture
        exposure_time (float): Exposure time of each frame
        devices (GenericCollectionDevices): The standard devices needed for the
                collection
        collection (Callable[[], MsgGenerator]): The collection logic, including
                triggering the detetcors
        baseline_devices (list[StandardReadable] | None, optional): Any other devices to
                record metadata from. Defaults to None.
    """
    MAX_TIME_BETWEEN_FRAMES = 0.1
    I0_DEADTIME = 0.0001

    # See https://github.com/DiamondLightSource/crystallography-bluesky/issues/56
    assert exposure_time < MAX_TIME_BETWEEN_FRAMES, (
        "This test does not work with long frames"
    )

    #  Workaround for https://github.com/bluesky/ophyd-async/issues/1288 for now
    yield from bps.abs_set(devices.fastcs_eiger.detector.ntrigger, frames, wait=True)

    eiger_trigger_info = TriggerInfo(
        collections_per_event=1,
        number_of_events=1,
        trigger=DetectorTrigger.EXTERNAL_EDGE,
        livetime=exposure_time,
    )

    i0_trigger_info = TriggerInfo(
        collections_per_event=frames,
        number_of_events=1,
        trigger=DetectorTrigger.EXTERNAL_EDGE,
        livetime=exposure_time,
        deadtime=I0_DEADTIME,
    )

    detectors = [devices.fastcs_eiger, devices.i0]
    metadata = metadata or {}
    metadata.update({"detectors": [detector.name for detector in detectors]})

    baseline_devices = baseline_devices or []
    LOGGER.info(f"Baseline devices: {baseline_devices}")

    def cleanup(*_):
        # Close the shutter
        yield from bps.mv(devices.fast_shutter, OpenClose.CLOSE)
        # If we fail whilst the soft in is high we will end up immediately triggering
        # the detector on the next run
        yield from bps.abs_set(devices.zebra.inputs.soft_in_1, 0, wait=True)

    @bpp.stage_decorator(detectors)
    @bpp.baseline_decorator(baseline_devices)
    @bpp.run_decorator(md=metadata)
    @bpp.contingency_decorator(final_plan=cleanup)
    def inner_run():

        LOGGER.info("Preparing eiger and i0")
        yield from bps.prepare(
            devices.fastcs_eiger, eiger_trigger_info, group="prepare"
        )
        yield from bps.prepare(devices.i0, i0_trigger_info, group="prepare")
        yield from bps.wait("prepare")

        yield from bps.declare_stream(*detectors, name="primary", collect=True)

        yield from bps.mv(devices.fast_shutter, OpenClose.OPEN)

        LOGGER.info("Kickoff eiger and i0")
        yield from bps.kickoff_all(*detectors, wait=True)

        yield from collection()

        LOGGER.info("Completing Capture")
        yield from bps.complete_all(*detectors, wait=True)

        LOGGER.info("Collecting")
        yield from bps.collect(*detectors, return_payload=False, name="primary")

    yield from inner_run()


def generic_per_step_collection(
    frames: int,
    exposure_time: float,
    per_step: Callable[[], MsgGenerator],
    devices: GenericCollectionDevices,
    baseline_devices: list[StandardReadable] | None = None,
    metadata: dict[str, Any] | None = None,
) -> MsgGenerator:
    """Take a collection with the eiger and i0 detectors. Metadata from the robot
    spinner, tth, and any other baseline devices will be added to the nexus file.
    The plan provided in `per_step` is what will be run for each scan point, after
    the detector has been triggered.

    Args:
        frames (int): Number of frames to capture
        exposure_time (float): Exposure time of each frame
        per_step (Callable[[], MsgGenerator]): The plan to run after each frame has been
                taken.
        devices (GenericCollectionDevices): The standard devices needed for the
                collection
        baseline_devices (list[StandardReadable] | None, optional): Any other devices to
                record metadata from. Defaults to None.
    """

    yield from setup_zebra_for_software_triggering(devices.zebra)

    def software_triggered_collection():
        LOGGER.info(f"Triggering i0 and eiger {frames} times")
        for _ in range(frames):
            yield from bps.abs_set(devices.zebra.inputs.soft_in_1, 1, wait=True)
            yield from bps.sleep(exposure_time)
            yield from bps.abs_set(devices.zebra.inputs.soft_in_1, 0, wait=True)
            yield from per_step()

    all_baseline_devices = get_default_baseline_devices(devices) + (
        baseline_devices or []
    )

    yield from setup_and_teardown_collection(
        frames=frames,
        exposure_time=exposure_time,
        devices=devices,
        collection=software_triggered_collection,
        baseline_devices=all_baseline_devices,
        metadata=metadata,
    )
