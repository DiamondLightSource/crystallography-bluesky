import bluesky.plan_stubs as bps
from bluesky.utils import MsgGenerator
from dodal.common import inject
from ophyd_async.fastcs.eiger import EigerDetector

eiger = inject("fastcs_eiger")


def eiger_hv_reset(
    time_for_reset_seconds: int = 600,
    minutes_to_wait_after_reset: int = 30,
    eiger: EigerDetector = eiger,
) -> MsgGenerator[None]:
    yield from bps.mv(eiger.detector.hv_reset_duration, time_for_reset_seconds)
    yield from bps.trigger(eiger.detector.hv_reset)
    yield from bps.sleep(time_for_reset_seconds + 60 * minutes_to_wait_after_reset)
