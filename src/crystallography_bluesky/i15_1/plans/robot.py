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
    yield from prepare_beamlne_for_robot_load(blower, cobra)
    sample = SampleLocation(puck, position)
    yield from bps.abs_set(robot, sample, wait=True)


def prepare_beamlne_for_robot_load(blower: Blower, cobra: Cobra):
    group = "safe_position_for_robot_load"
    # Assuming they can move at the same time with no collision possibility?
    yield from bps.abs_set(
        blower.position, TemperatureControllerPosition.SAFE, group=group
    )
    yield from bps.abs_set(
        cobra.position, TemperatureControllerPosition.SAFE, group=group
    )
    yield from bps.wait(group)
