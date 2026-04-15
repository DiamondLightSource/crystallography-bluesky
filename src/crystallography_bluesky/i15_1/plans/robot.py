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
    hutch_status = yield from bps.rd(hutch_interlock.status)
    assert hutch_status == HUTCH_SAFE_FOR_OPERATIONS, (
        f"Hutch status was not {HUTCH_SAFE_FOR_OPERATIONS}, but instead {hutch_status}."
    )

    gonio_status = yield from bps.rd(gonio_interlock.status)
    assert gonio_status == GONIO_SAFE_FOR_OPERATIONS, (
        f"Goniometer interlock was not {GONIO_SAFE_FOR_OPERATIONS}, \
            but instead {gonio_status}"
    )

    sample = SampleLocation(puck, position)
    yield from bps.abs_set(robot, sample, wait=True)


def robot_unload(
    robot: Robot = robot,
    hutch_interlock: HutchInterlock = hutch_interlock,
) -> MsgGenerator[None]:
    hutch_status = yield from bps.rd(hutch_interlock.status)
    assert hutch_status == HUTCH_SAFE_FOR_OPERATIONS, (
        f"Hutch status was not 0, but instead {hutch_status}."
    )

    yield from bps.abs_set(robot, SAMPLE_LOCATION_EMPTY, wait=True)
