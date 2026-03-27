from bluesky import plan_stubs as bps
from bluesky.utils import MsgGenerator
from dodal.common import inject
from dodal.devices.beamlines.i15_1.robot import (
    SAMPLE_LOCATION_EMPTY,
    Robot,
    SampleLocation,
)


def robot_load(
    puck: int, position: int, robot: Robot = inject("robot")
) -> MsgGenerator[None]:
    sample = SampleLocation(puck, position)
    yield from bps.abs_set(robot, sample, wait=True)


def robot_unload(robot: Robot = inject("robot")) -> MsgGenerator[None]:
    yield from bps.abs_set(robot, SAMPLE_LOCATION_EMPTY, wait=True)
