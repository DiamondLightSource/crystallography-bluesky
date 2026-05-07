from bluesky import plan_stubs as bps
from bluesky.utils import MsgGenerator
from dodal.common import inject
from dodal.devices.beamlines.i15_1.robot import (
    SAMPLE_LOCATION_EMPTY,
    Robot,
    SampleLocation,
)
from dodal.devices.interlocks import IntPLCInterlock, PSSInterlock
from dodal.devices.motors import XYZStage

robot = inject("robot")
hutch_interlock = inject("hutch_interlock")
gonio_interlock = inject("gonio_interlock")
hexapod = inject("hexapod")
hexapod_rotation = inject("hexapod_rotation")

HUTCH_SAFE_FOR_OPERATIONS = 0
GONIO_SAFE_FOR_OPERATIONS = 65535  # All 16 bits are true


def robot_load(
    puck: int,
    position: int,
    robot: Robot = robot,
    hutch_interlock: PSSInterlock = hutch_interlock,
    gonio_interlock: IntPLCInterlock = gonio_interlock,
    hexapod: XYZStage = hexapod,
    hexapod_rotation: XYZStage = hexapod_rotation,
) -> MsgGenerator[None]:
    gonio_status = yield from bps.rd(gonio_interlock.is_safe)
    assert gonio_status is True, "Goniometer interlock status was not safe to operate."

    hutch_status = yield from bps.rd(hutch_interlock.is_safe)
    assert hutch_status is True, (
        "Experimental hutch interlock status was not safe to operate."
    )

    yield from move_hexapod_to_home_position(hexapod, hexapod_rotation)

    sample = SampleLocation(puck, position)
    yield from bps.abs_set(robot, sample, wait=True)


def robot_unload(
    robot: Robot = robot,
    hutch_interlock: PSSInterlock = hutch_interlock,
    gonio_interlock: IntPLCInterlock = gonio_interlock,
    hexapod: XYZStage = hexapod,
    hexapod_rotation: XYZStage = hexapod_rotation,
) -> MsgGenerator[None]:
    gonio_status = yield from bps.rd(gonio_interlock.is_safe)
    assert gonio_status is True, "Goniometer interlock status was not safe to operate."

    hutch_status = yield from bps.rd(hutch_interlock.is_safe)
    assert hutch_status is True, (
        "Experimental hutch interlock status was not safe to operate."
    )

    yield from move_hexapod_to_home_position(hexapod, hexapod_rotation)

    yield from bps.abs_set(robot, SAMPLE_LOCATION_EMPTY, wait=True)


def move_hexapod_to_home_position(
    hexapod: XYZStage = hexapod,
    hexapod_rotation: XYZStage = hexapod_rotation,
    x_home: float = 0.0,
    y_home: float = 0.0,
    z_home: float = 0.0,
    rx_home: float = 0.0,
    ry_home: float = 0.0,
    rz_home: float = 0.0,
    group: str = "hexapod_move_home_group",
) -> MsgGenerator[None]:
    yield from bps.abs_set(hexapod.x, x_home, group=group)
    yield from bps.abs_set(hexapod.y, y_home, group=group)
    yield from bps.abs_set(hexapod.z, z_home, group=group)
    yield from bps.abs_set(hexapod_rotation.x, rx_home, group=group)
    yield from bps.abs_set(hexapod_rotation.y, ry_home, group=group)
    yield from bps.abs_set(hexapod_rotation.z, rz_home, group=group)

    yield from bps.wait(group=group)
