import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
from bluesky.utils import MsgGenerator
from ophyd_async.core import TriggerInfo
from ophyd_async.epics.adcore import ContAcqDetector


@bpp.run_decorator()
def take_snapshot(camera: ContAcqDetector) -> MsgGenerator:
    yield from bps.stage(camera)
    yield from bps.prepare(camera, TriggerInfo(number_of_events=1), wait=True)
    yield from bps.trigger_and_read([camera])
    yield from bps.unstage(camera)
