import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
from bluesky.utils import MsgGenerator
from dodal.common import inject
from dodal.devices.beamlines.i15_1.robot import Robot
from dodal.devices.tetramm import TetrammDetector
from dodal.devices.zebra.zebra import Zebra
from dodal.log import LOGGER
from ophyd_async.core import DetectorTrigger, StandardReadable, TriggerInfo
from ophyd_async.epics.motor import Motor
from ophyd_async.fastcs.eiger import EigerDetector

eiger = inject("fastcs_eiger")
i0 = inject("i0")
zebra = inject("zebra")
robot = inject("robot")
tth = inject("tth")


def static_collection_plan(
    frames: int,
    exposure_time: float,
    eiger: EigerDetector = eiger,
    i0: TetrammDetector = i0,
    zebra: Zebra = zebra,
    robot: Robot = robot,
    tth: Motor = tth,
    baseline_devices: list[StandardReadable] | None = None,
) -> MsgGenerator:
    """Take a static collection with the eiger and i0 detectors. Currently the i0 is
    triggered by the zebra and the eiger is triggered manually. Metadata from the robot
    spinner, tth, and any other baseline devices will be added to the nexus file.

    Args:
        frames (int): Number of frames to capture
        exposure_time (float): Exposure time of each frame
        eiger (EigerDetector, optional): FastCS eiger device.
        i0 (TetrammDetector, optional): i0 device.
        zebra (Zebra, optional): Zebra device.
        robot (Robot, optional): Robot device, needed for spinner metadata.
        tth (Motor, optional): Two theta device, needed for eiger angle metadata.
        baseline_devices (list[StandardReadable] | None, optional): Any other devices to
        record metadata from. Defaults to None.
    """
    DEFAULT_BASELINE_DEVICES = [robot.spinner, tth]
    TIME_BETWEEN_FRAMES = 0.1
    I0_DEADTIME = 0.0001

    # See https://github.com/DiamondLightSource/crystallography-bluesky/issues/56
    assert exposure_time < TIME_BETWEEN_FRAMES, (
        "This test does not work with long frames"
    )

    eiger_trigger_info = TriggerInfo(
        collections_per_event=1,
        number_of_events=1,
        trigger=DetectorTrigger.INTERNAL,
        livetime=exposure_time,
    )

    i0_trigger_info = TriggerInfo(
        collections_per_event=frames,
        number_of_events=1,
        trigger=DetectorTrigger.EXTERNAL_EDGE,
        livetime=exposure_time,
        deadtime=I0_DEADTIME,
    )

    detectors = [eiger, i0]
    baseline_devices = DEFAULT_BASELINE_DEVICES + (baseline_devices or [])
    LOGGER.info(f"Baseline devices: {baseline_devices}")

    @bpp.baseline_decorator(baseline_devices)
    @bpp.stage_decorator(detectors)
    @bpp.run_decorator()
    def inner_run():
        LOGGER.info("Preparing eiger and i0")
        yield from bps.prepare(eiger, eiger_trigger_info, group="prepare")
        yield from bps.prepare(i0, i0_trigger_info, group="prepare")
        yield from bps.wait("prepare")

        yield from bps.declare_stream(*detectors, name="primary", collect=True)

        LOGGER.info("Kickoff eiger and i0")
        yield from bps.kickoff_all(*detectors, wait=True)

        LOGGER.info(f"Triggering i0 and eiger {frames} times")
        for i in range(frames):
            yield from bps.trigger(eiger.detector.trigger, group=f"trigger_{i}")
            yield from bps.abs_set(zebra.inputs.soft_in_1, 1, group=f"trigger_{i}")
            yield from bps.wait(f"trigger_{i}")
            yield from bps.sleep(TIME_BETWEEN_FRAMES)
            yield from bps.abs_set(zebra.inputs.soft_in_1, 0, wait=True)

        LOGGER.info("Completing Capture")
        yield from bps.complete_all(*detectors, wait=True)

        LOGGER.info("Collecting")
        yield from bps.collect(*detectors, return_payload=False, name="primary")

    LOGGER.info("Unstaging eiger and i0")
    yield from bps.unstage_all(*detectors)

    yield from inner_run()
