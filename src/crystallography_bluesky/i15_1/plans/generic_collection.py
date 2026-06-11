from collections.abc import Callable

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
import pydantic
from bluesky.utils import MsgGenerator
from dodal.common import inject
from dodal.devices.beamlines.i15_1.laue import LaueMonochrometer
from dodal.devices.beamlines.i15_1.robot import Robot
from dodal.devices.tetramm import TetrammDetector
from dodal.devices.zebra.zebra import Zebra
from dodal.devices.zebra.zebra_controlled_shutter import OpenClose, ZebraFastShutter
from dodal.log import LOGGER
from ophyd_async.core import DetectorTrigger, StandardReadable, TriggerInfo
from ophyd_async.epics.motor import Motor
from ophyd_async.fastcs.eiger import EigerDetector

devices = inject("")


@pydantic.dataclasses.dataclass(config={"arbitrary_types_allowed": True})
class GenericCollectionDevices:
    fastcs_eiger: EigerDetector
    i0: TetrammDetector
    zebra: Zebra
    robot: Robot
    tth: Motor
    fast_shutter: ZebraFastShutter
    xtal: LaueMonochrometer


def generic_collection(
    frames: int,
    exposure_time: float,
    per_step: Callable[[], MsgGenerator],
    devices: GenericCollectionDevices,
    baseline_devices: list[StandardReadable] | None = None,
) -> MsgGenerator:
    """Take a collection with the eiger and i0 detectors. Metadata from the robot
    spinner, tth, and any other baseline devices will be added to the nexus file.

    Args:
        frames (int): Number of frames to capture
        exposure_time (float): Exposure time of each frame
        per_step (Callable[[], MsgGenerator]): The plan to run on each frame
        devices (GenericCollectionDevices): The standard devices needed for the
                collection
        baseline_devices (list[StandardReadable] | None, optional): Any other devices to
                record metadata from. Defaults to None.
    """
    DEFAULT_BASELINE_DEVICES = [devices.robot.spinner, devices.tth, devices.xtal]
    TIME_BETWEEN_FRAMES = 0.1
    I0_DEADTIME = 0.0001

    # See https://github.com/DiamondLightSource/crystallography-bluesky/issues/56
    assert exposure_time < TIME_BETWEEN_FRAMES, (
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
    baseline_devices = DEFAULT_BASELINE_DEVICES + (baseline_devices or [])
    LOGGER.info(f"Baseline devices: {baseline_devices}")

    def cleanup(*_):
        # Close the shutter
        yield from bps.mv(devices.fast_shutter, OpenClose.CLOSE)
        # If we fail whilst the soft in is high we will end up immediately triggering
        # the detector on the next run
        yield from bps.abs_set(devices.zebra.inputs.soft_in_1, 0, wait=True)

    @bpp.stage_decorator(detectors)
    @bpp.baseline_decorator(baseline_devices)
    @bpp.run_decorator()
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

        LOGGER.info(f"Triggering i0 and eiger {frames} times")
        for _ in range(frames):
            yield from bps.abs_set(devices.zebra.inputs.soft_in_1, 1, wait=True)
            yield from bps.sleep(exposure_time)
            yield from bps.abs_set(devices.zebra.inputs.soft_in_1, 0, wait=True)
            yield from per_step()

        LOGGER.info("Completing Capture")
        yield from bps.complete_all(*detectors, wait=True)

        LOGGER.info("Collecting")
        yield from bps.collect(*detectors, return_payload=False, name="primary")

    yield from inner_run()
