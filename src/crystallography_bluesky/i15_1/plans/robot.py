from bluesky import plan_stubs as bps
from bluesky.utils import MsgGenerator
from dodal.common import inject
from dodal.devices.beamlines.i15_1.blower import Blower
from dodal.devices.beamlines.i15_1.cobra import Cobra
from dodal.devices.beamlines.i15_1.robot import Robot, SampleLocation
from dodal.devices.beamlines.i15_1.temperature_controller import (
    TemperatureControllerPosition,
)


def robot_load(
    puck: int,
    position: int,
    robot: Robot = inject("robot"),
    blower: Blower = inject("blower_y"),
    cobra: Cobra = inject("cobra"),
) -> MsgGenerator[None]:
    yield from prepare_beamline_for_robot_load(blower, cobra)
    sample = SampleLocation(puck, position)
    yield from bps.abs_set(robot, sample, wait=True)


def prepare_beamline_for_robot_load(blower: Blower, cobra: Cobra) -> MsgGenerator[None]:
    group = "safe_position_for_robot_load"
    yield from bps.abs_set(blower, TemperatureControllerPosition.SAFE, group=group)
    yield from bps.abs_set(cobra, TemperatureControllerPosition.SAFE, group=group)
    yield from bps.wait(group)


def move_devices_to_beam_position(blower: Blower, cobra: Cobra) -> MsgGenerator[None]:
    group = "safe_position_for_robot_load"
    yield from bps.abs_set(blower, TemperatureControllerPosition.BEAM, group=group)
    yield from bps.abs_set(cobra, TemperatureControllerPosition.BEAM, group=group)
    yield from bps.wait(group)
