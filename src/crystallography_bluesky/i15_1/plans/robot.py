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
    yield from move_devices_to_safe_position(blower, cobra)
    sample = SampleLocation(puck, position)
    yield from bps.abs_set(robot, sample, wait=True)


def move_devices_to_safe_position(blower: Blower, cobra: Cobra):
    group = "safe_position"
    yield from bps.abs_set(
        blower.position, TemperatureControllerPosition.SAFE, group=group
    )
    yield from bps.abs_set(cobra.position, True, group=group)
    yield from bps.wait(group)
