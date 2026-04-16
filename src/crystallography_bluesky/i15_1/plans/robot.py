from bluesky import plan_stubs as bps
from bluesky.utils import MsgGenerator
from dodal.common import inject
from dodal.devices.beamlines.i15_1.blower import Blower
from dodal.devices.beamlines.i15_1.cobra import Cobra
from dodal.devices.beamlines.i15_1.robot import Robot, SampleLocation
from dodal.devices.beamlines.i15_1.safe_or_beam_positioner import (
    SafeOrBeamPosition,
)


def robot_load(
    puck: int,
    position: int,
    robot: Robot = inject("robot"),
    blower: Blower = inject("blower_z"),
    cobra: Cobra = inject("cobra"),
) -> MsgGenerator[None]:
    yield from prepare_beamline_for_robot_load(blower, cobra)
    sample = SampleLocation(puck, position)
    yield from bps.abs_set(robot, sample, wait=True)


def prepare_beamline_for_robot_load(
    blower: Blower = inject("blower"), cobra: Cobra = inject("cobra")
) -> MsgGenerator[None]:
    group = "safe_position_for_robot_load"
    yield from bps.abs_set(blower, SafeOrBeamPosition.SAFE, group=group)
    yield from bps.abs_set(cobra, SafeOrBeamPosition.SAFE, group=group)
    yield from bps.wait(group)


def move_devices_to_beam_position(
    blower: Blower = inject("blower"), cobra: Cobra = inject("cobra")
) -> MsgGenerator[None]:
    group = "safe_position_for_robot_load"
    yield from bps.abs_set(blower, SafeOrBeamPosition.BEAM, group=group)
    yield from bps.abs_set(cobra, SafeOrBeamPosition.BEAM, group=group)
    yield from bps.wait(group)
