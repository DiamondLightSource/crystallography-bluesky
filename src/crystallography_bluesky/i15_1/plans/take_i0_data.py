import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
from bluesky.utils import MsgGenerator
from dodal.common import inject
from dodal.devices.tetramm import TetrammDetector
from dodal.devices.zebra.zebra import Zebra
from dodal.log import LOGGER
from ophyd_async.core import StandardReadable
from ophyd_async.core._detector import DetectorTrigger, TriggerInfo

i0 = inject("i0")
zebra = inject("zebra")


def take_i0_data(
    frames: int,
    exposure_time: float,
    i0: TetrammDetector = i0,
    zebra: Zebra = zebra,
    baseline_devices: list[StandardReadable] | None = None,
) -> MsgGenerator:
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
        LOGGER.info("Preparing i0")
        yield from bps.prepare(i0, trigger_info, wait=True)

        yield from bps.declare_stream(i0, name="primary", collect=True)

        LOGGER.info("Kickoff i0")
        yield from bps.kickoff(i0, wait=True)

        LOGGER.info(f"Triggering i0 {frames} times")
        for _ in range(frames):
            yield from bps.abs_set(zebra.inputs.soft_in_1, 1, wait=True)
            yield from bps.sleep(TIME_BETWEEN_FRAMES)
            yield from bps.abs_set(zebra.inputs.soft_in_1, 0, wait=True)

        LOGGER.info("Completing Capture")
        yield from bps.complete(i0, wait=True)

        LOGGER.info("Collecting")
        yield from bps.collect(i0, return_payload=False, name="primary")

    LOGGER.info("Unstaging i0")
    yield from bps.unstage(i0, wait=True)

    yield from inner_run()
