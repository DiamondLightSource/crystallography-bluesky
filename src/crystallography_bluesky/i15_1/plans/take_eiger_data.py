import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
from bluesky.utils import MsgGenerator
from dodal.common import inject
from dodal.log import LOGGER
from ophyd_async.core import (
    StandardReadable,
    TriggerInfo,
)
from ophyd_async.fastcs.eiger import EigerDetector

eiger = inject("fastcs_eiger")


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
        yield from bps.prepare(eiger, trigger_info, wait=True)
        LOGGER.info("Preparing Eiger")

        yield from bps.declare_stream(eiger, name="primary", collect=True)

        yield from bps.kickoff(eiger, wait=True)
        LOGGER.info("Kickoff Eiger")

        yield from bps.trigger(eiger.detector.trigger, wait=True)
        LOGGER.info("Triggering Eiger")

        yield from bps.complete(eiger, wait=True)
        LOGGER.info("Completing Capture")

        yield from bps.collect(eiger, return_payload=False, name="primary")
        LOGGER.info("Collecting")

    yield from bps.unstage(eiger, wait=True)
    LOGGER.info("Unstaging Eiger-Odin")

    yield from bps.stage(eiger, wait=True)
    LOGGER.info("Staging Eiger-Odin")

    yield from bps.abs_set(eiger.od.fp.data_chunks_0, 1, wait=True)
    LOGGER.info("Setting # of Frame Chunks")

    yield from inner_run()

    yield from bps.unstage(eiger, wait=True)
    LOGGER.info("Disarming Eiger")
