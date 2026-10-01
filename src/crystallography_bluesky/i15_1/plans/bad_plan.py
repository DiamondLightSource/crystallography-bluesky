import bluesky.plan_stubs as bps
from bluesky.utils import MsgGenerator


def bad_plan() -> MsgGenerator:
    yield from bps.null()
    raise Exception()
