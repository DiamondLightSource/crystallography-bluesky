import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
from bluesky.utils import MsgGenerator
from dodal.common import inject
from dodal.devices.tetramm import TetrammDetector
from dodal.devices.zebra.zebra import Zebra
from dodal.log import LOGGER
from ophyd_async.core import DetectorTrigger, StandardReadable, TriggerInfo
from ophyd_async.fastcs.eiger import EigerDetector

eiger = inject("fastcs_eiger")
i0 = inject("i0")
zebra = inject("zebra")


def take_eiger_data(
    frames: int,
    exposure_time: float,
    eiger: EigerDetector = eiger,
    baseline_devices: list[StandardReadable] | None = None,
) -> MsgGenerator:
    trigger_info = TriggerInfo(
        collections_per_event=frames, number_of_events=1, livetime=exposure_time
    )

    @bpp.baseline_decorator(baseline_devices or [])
    @bpp.run_decorator()
    def inner_run():
        LOGGER.info("Preparing Eiger")
        yield from bps.prepare(eiger, trigger_info, wait=True)

        yield from bps.declare_stream(eiger, name="primary", collect=True)

        LOGGER.info("Kickoff Eiger")
        yield from bps.kickoff(eiger, wait=True)

        LOGGER.info("Triggering Eiger")
        yield from bps.trigger(eiger.detector.trigger, wait=True)

        LOGGER.info("Completing Capture")
        yield from bps.complete(eiger, wait=True)

        LOGGER.info("Collecting")
        yield from bps.collect(eiger, return_payload=False, name="primary")

    LOGGER.info("Unstaging Eiger-Odin")
    yield from bps.unstage(eiger, wait=True)

    LOGGER.info("Staging Eiger-Odin")
    yield from bps.stage(eiger, wait=True)

    yield from inner_run()

    LOGGER.info("Disarming Eiger")
    yield from bps.unstage(eiger, wait=True)


def take_eiger_and_i0_data(
    frames: int,
    exposure_time: float,
    eiger: EigerDetector = eiger,
    i0: TetrammDetector = i0,
    zebra: Zebra = zebra,
    baseline_devices: list[StandardReadable] | None = None,
):
    TIME_BETWEEN_FRAMES = 0.1
    assert exposure_time < TIME_BETWEEN_FRAMES, (
        "This test does not work with long frames"
    )

    trigger_info = TriggerInfo(
        collections_per_event=frames,
        trigger=DetectorTrigger.EXTERNAL_EDGE,
        livetime=exposure_time,
        deadtime=0.0001,
    )

    @bpp.baseline_decorator(baseline_devices or [])
    @bpp.stage_decorator([i0])
    @bpp.run_decorator()
    def inner_run():
        LOGGER.info("Preparing eiger and i0")
        yield from bps.prepare(eiger, trigger_info, group="prepare")
        yield from bps.prepare(i0, trigger_info, group="prepare")
        yield from bps.wait("prepare")

        yield from bps.declare_stream(eiger, name="primary", collect=True)
        yield from bps.declare_stream(i0, name="primary", collect=True)

        LOGGER.info("Kickoff eiger and i0")
        yield from bps.kickoff(eiger, group="kickoff")
        yield from bps.kickoff(i0, group="kickoff")
        yield from bps.wait("kickoff")

        LOGGER.info(f"Triggering eiger and i0 {frames} times")
        for i in range(frames):
            yield from bps.abs_set(zebra.inputs.soft_in_1, 1, group=f"trigger_{i}")
            yield from bps.trigger(eiger.detector.trigger, group=f"trigger_{i}")
            yield from bps.wait(f"trigger_{i}")
            yield from bps.sleep(TIME_BETWEEN_FRAMES)
            yield from bps.abs_set(zebra.inputs.soft_in_1, 0, wait=True)

        LOGGER.info("Completing Capture")
        yield from bps.complete(eiger, group="complete")
        yield from bps.complete(i0, group="complete")
        yield from bps.wait("complete")

        LOGGER.info("Collecting")
        yield from bps.collect(eiger, return_payload=False, name="primary")
        yield from bps.collect(i0, return_payload=False, name="primary")

    yield from inner_run()
