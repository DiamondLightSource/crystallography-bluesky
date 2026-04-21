from math import isclose

from bluesky import plan_stubs as bps
from bluesky.utils import MsgGenerator
from dodal.common import inject
from dodal.devices.beamlines.i15_1.gonio_interlock import GonioInterlock
from dodal.devices.beamlines.i15_1.robot import (
    SAMPLE_LOCATION_EMPTY,
    Robot,
    SampleLocation,
)
from dodal.devices.hutch_shutter import BaseHutchInterlock, HutchInterlock

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
    yield from _check_interlock_status_is_close(
        hutch_interlock, HUTCH_SAFE_FOR_OPERATIONS
    )
    yield from _check_interlock_status_is_close(
        gonio_interlock, GONIO_SAFE_FOR_OPERATIONS
    )

    sample = SampleLocation(puck, position)
    yield from bps.abs_set(robot, sample, wait=True)


def robot_unload(
    robot: Robot = robot,
    hutch_interlock: HutchInterlock = hutch_interlock,
    gonio_interlock: GonioInterlock = gonio_interlock,
) -> MsgGenerator[None]:
    yield from _check_interlock_status_is_close(
        hutch_interlock, HUTCH_SAFE_FOR_OPERATIONS
    )
    yield from _check_interlock_status_is_close(
        gonio_interlock, GONIO_SAFE_FOR_OPERATIONS
    )

    yield from bps.abs_set(robot, SAMPLE_LOCATION_EMPTY, wait=True)


def check_gonio_interlock(
    gonio_interlock: GonioInterlock = gonio_interlock,
) -> MsgGenerator[None]:
    yield from _check_interlock_status_is_close(
        gonio_interlock, GONIO_SAFE_FOR_OPERATIONS
    )


def check_hutch_interlock(
    hutch_interlock: HutchInterlock = hutch_interlock,
) -> MsgGenerator[None]:
    yield from _check_interlock_status_is_close(
        hutch_interlock, HUTCH_SAFE_FOR_OPERATIONS
    )


def _check_interlock_status_is_close(
    interlock: BaseHutchInterlock, status_safe_for_operations: int | float
) -> MsgGenerator:
    status = yield from bps.rd(interlock.status)
    assert isclose(float(status), float(status_safe_for_operations), abs_tol=5e-2), (
        f"Interlock status was not {status_safe_for_operations}, but instead {status}."
    )
