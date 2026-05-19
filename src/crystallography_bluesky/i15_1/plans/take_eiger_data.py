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
