from bluesky import plan_stubs as bps
from bluesky.utils import MsgGenerator
from dodal.common import inject
from dodal.devices.beamlines.i15_1.robot import Robot, SampleLocation


def robot_load(
    puck: int, position: int, robot: Robot = inject("robot")
) -> MsgGenerator[None]:
    sample = SampleLocation(puck, position)
    yield from bps.abs_set(robot, sample, wait=True)
