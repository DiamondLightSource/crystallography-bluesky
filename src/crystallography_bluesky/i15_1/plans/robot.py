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
from dodal.devices.motors import XYZStage

robot = inject("robot")
hutch_interlock = inject("hutch_interlock")
gonio_interlock = inject("gonio_interlock")
hexapod = inject("hexapod")
hexapod_rot = inject("hexapod_rot")

HUTCH_SAFE_FOR_OPERATIONS = 0
GONIO_SAFE_FOR_OPERATIONS = 65535  # All 16 bits are true


def robot_load(
    puck: int,
    position: int,
    robot: Robot = robot,
    hutch_interlock: HutchInterlock = hutch_interlock,
    gonio_interlock: GonioInterlock = gonio_interlock,
    hexapod: XYZStage = hexapod,
    hexapod_rot: XYZStage = hexapod_rot,
) -> MsgGenerator[None]:
    gonio_status = yield from bps.rd(gonio_interlock.is_safe)
    assert gonio_status is True, "Goniometer interlock status was not safe to operate."

    hutch_status = yield from bps.rd(hutch_interlock.is_safe)
    assert hutch_status is True, (
        "Experimental hutch interlock status was not safe to operate."
    )

    yield from move_hexapod_to_home_position(hexapod, hexapod_rot)

    sample = SampleLocation(puck, position)
    yield from bps.abs_set(robot, sample, wait=True)


def robot_unload(
    robot: Robot = robot,
    hutch_interlock: HutchInterlock = hutch_interlock,
    gonio_interlock: GonioInterlock = gonio_interlock,
    hexapod: XYZStage = hexapod,
    hexapod_rot: XYZStage = hexapod_rot,
) -> MsgGenerator[None]:
    gonio_status = yield from bps.rd(gonio_interlock.is_safe)
    assert gonio_status is True, "Goniometer interlock status was not safe to operate."

    hutch_status = yield from bps.rd(hutch_interlock.is_safe)
    assert hutch_status is True, (
        "Experimental hutch interlock status was not safe to operate."
    )

    yield from move_hexapod_to_home_position(hexapod, hexapod_rot)

    yield from bps.abs_set(robot, SAMPLE_LOCATION_EMPTY, wait=True)


def move_hexapod_to_home_position(
    hexapod: XYZStage = hexapod,
    hexapod_rot: XYZStage = hexapod_rot,
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
    yield from bps.abs_set(hexapod_rot.x, rx_home, group=group)
    yield from bps.abs_set(hexapod_rot.y, ry_home, group=group)
    yield from bps.abs_set(hexapod_rot.z, rz_home, group=group)

    yield from bps.wait(group=group)
