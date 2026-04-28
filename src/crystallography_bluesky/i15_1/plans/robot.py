from bluesky import plan_stubs as bps
from bluesky.utils import MsgGenerator
from dodal.common import inject
from dodal.devices.beamlines.i15_1.gonio_interlock import GonioInterlock
from dodal.devices.beamlines.i15_1.robot import (
    SAMPLE_LOCATION_EMPTY,
    Robot,
    SampleLocation,
)
from dodal.devices.hutch_shutter import HutchInterlock

robot = inject("robot")
hutch_interlock = inject("hutch_interlock")
gonio_interlock = inject("gonio_interlock")

HUTCH_SAFE_FOR_OPERATIONS = 0
GONIO_SAFE_FOR_OPERATIONS = 65535  # All 16 bits are true


def robot_load(
    puck: int,
    position: int,
    robot: Robot = robot,
    hutch_interlock: HutchInterlock = hutch_interlock,
    gonio_interlock: GonioInterlock = gonio_interlock,
) -> MsgGenerator[None]:
    gonio_status = yield from bps.rd(gonio_interlock.is_safe)
    assert gonio_status is True, "Goniometer interlock status was not safe to operate."

    hutch_status = yield from bps.rd(hutch_interlock.is_safe)
    assert hutch_status is True, (
        "Experimental hutch interlock status was not safe to operate."
    )

    sample = SampleLocation(puck, position)
    yield from bps.abs_set(robot, sample, wait=True)


def robot_unload(
    robot: Robot = robot,
    hutch_interlock: HutchInterlock = hutch_interlock,
    gonio_interlock: GonioInterlock = gonio_interlock,
) -> MsgGenerator[None]:
    gonio_status = yield from bps.rd(gonio_interlock.is_safe)
    assert gonio_status is True, "Goniometer interlock status was not safe to operate."

    hutch_status = yield from bps.rd(hutch_interlock.is_safe)
    assert hutch_status is True, (
        "Experimental hutch interlock status was not safe to operate."
    )

    yield from bps.abs_set(robot, SAMPLE_LOCATION_EMPTY, wait=True)
