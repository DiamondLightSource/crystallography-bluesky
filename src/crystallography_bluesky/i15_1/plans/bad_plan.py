import bluesky.plan_stubs as bps
from bluesky.utils import MsgGenerator


def bad_plan(message: str | None = None) -> MsgGenerator:
    yield from bps.null()
    raise Exception(message)
