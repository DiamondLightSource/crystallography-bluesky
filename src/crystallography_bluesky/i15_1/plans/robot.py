from collections.abc import Hashable

from bluesky import plan_stubs as bps
from bluesky.utils import MsgGenerator
from dodal.common import inject
from dodal.devices.beamlines.i15_1.blower import Blower
from dodal.devices.beamlines.i15_1.cobra import Cobra
from dodal.devices.beamlines.i15_1.hexapod import Hexapod
from dodal.devices.beamlines.i15_1.robot import (
    SAMPLE_LOCATION_EMPTY,
    Robot,
    SampleLocation,
    SpinnerState,
)
from dodal.devices.beamlines.i15_1.safe_or_beam_positioner import (
    SafeOrBeamPosition,
)
from dodal.devices.interlocks import IntPLCInterlock, PSSInterlock
from dodal.log import LOGGER

robot = inject("robot")
hutch_interlock = inject("hutch_interlock")
blower = inject("blower")
cobra = inject("cobra")
gonio_interlock = inject("gonio_interlock")
hexapod = inject("hexapod")

HUTCH_SAFE_FOR_OPERATIONS = 0
GONIO_SAFE_FOR_OPERATIONS = 65535  # All 16 bits are true


def prepare_beamline_for_robot_action(
    blower: Blower = blower,
    cobra: Cobra = cobra,
    hutch_interlock: PSSInterlock = hutch_interlock,
    gonio_interlock: IntPLCInterlock = gonio_interlock,
    hexapod: Hexapod = hexapod,
) -> MsgGenerator[None]:
    gonio_status = yield from bps.rd(gonio_interlock.is_safe)
    assert gonio_status is True, "Goniometer interlock status was not safe to operate."

    hutch_status = yield from bps.rd(hutch_interlock.is_safe)
    assert hutch_status is True, (
        "Experimental hutch interlock status was not safe to operate."
    )

    group = "safe_position_for_robot_action"

    yield from move_hexapod_to_home_position(hexapod, group=group)

    yield from bps.abs_set(blower, SafeOrBeamPosition.SAFE, group=group)
    # Cobra currently is not mounted on the beamline
    # yield from bps.abs_set(cobra, SafeOrBeamPosition.SAFE, group=group)
    LOGGER.warning("Skipping cobra move")
    yield from bps.wait(group)


def robot_load(
    puck: int,
    position: int,
    turn_spinner_on: bool = True,
    robot: Robot = robot,
    hutch_interlock: PSSInterlock = hutch_interlock,
    gonio_interlock: IntPLCInterlock = gonio_interlock,
    hexapod: Hexapod = hexapod,
    blower: Blower = blower,
    cobra: Cobra = cobra,
) -> MsgGenerator[None]:
    yield from prepare_beamline_for_robot_action(
        blower, cobra, hutch_interlock, gonio_interlock, hexapod
    )

    sample = SampleLocation(puck, position)
    yield from bps.abs_set(robot, sample, wait=True)

    if turn_spinner_on:
        yield from bps.abs_set(robot.spinner, SpinnerState.ON, wait=True)


def robot_unload(
    robot: Robot = robot,
    hutch_interlock: PSSInterlock = hutch_interlock,
    gonio_interlock: IntPLCInterlock = gonio_interlock,
    hexapod: Hexapod = hexapod,
    blower: Blower = blower,
    cobra: Cobra = cobra,
) -> MsgGenerator[None]:
    yield from prepare_beamline_for_robot_action(
        blower, cobra, hutch_interlock, gonio_interlock, hexapod
    )

    yield from bps.abs_set(robot, SAMPLE_LOCATION_EMPTY, wait=True)


def move_hexapod_to_home_position(
    hexapod: Hexapod = hexapod,
    x_home: float = 0.0,
    y_home: float = 0.0,
    z_home: float = 0.0,
    rx_home: float = 0.0,
    ry_home: float = 0.0,
    rz_home: float = 0.0,
    group: Hashable | None = None,
    wait: bool = True,
) -> MsgGenerator[None]:
    yield from bps.abs_set(
        hexapod,
        {
            "x": x_home,
            "y": y_home,
            "z": z_home,
            "rx": rx_home,
            "ry": ry_home,
            "rz": rz_home,
        },
        group=group,
        wait=wait,
    )
