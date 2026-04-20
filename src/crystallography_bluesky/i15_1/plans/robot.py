from bluesky import plan_stubs as bps
from bluesky.utils import MsgGenerator
from dodal.common import inject
from dodal.devices.beamlines.i15_1.blower import Blower
from dodal.devices.beamlines.i15_1.cobra import Cobra
from dodal.devices.beamlines.i15_1.robot import (
    SAMPLE_LOCATION_EMPTY,
    Robot,
    SampleLocation,
)
from dodal.devices.beamlines.i15_1.safe_or_beam_positioner import (
    SafeOrBeamPosition,
)
from dodal.devices.hutch_shutter import HutchInterlock

robot = inject("robot")
hutch_interlock = inject("hutch_interlock")
blower = inject("blower_z")
cobra = inject("cobra")

HUTCH_SAFE_FOR_OPERATIONS = 0


def robot_load(
    puck: int,
    position: int,
    robot: Robot = robot,
    hutch_interlock: HutchInterlock = hutch_interlock,
    blower: Blower = blower,
    cobra: Cobra = cobra,
) -> MsgGenerator[None]:

    hutch_status = yield from bps.rd(hutch_interlock.status)
    assert hutch_status == HUTCH_SAFE_FOR_OPERATIONS, (
        f"Hutch status was not 0, but instead {hutch_status}."
    )
    yield from prepare_beamline_for_robot_load(blower, cobra)

    sample = SampleLocation(puck, position)
    yield from bps.abs_set(robot, sample, wait=True)


def prepare_beamline_for_robot_load(
    blower: Blower = blower, cobra: Cobra = cobra
) -> MsgGenerator[None]:
    group = "safe_position_for_robot_load"
    yield from bps.abs_set(blower, SafeOrBeamPosition.SAFE, group=group)
    yield from bps.abs_set(cobra, SafeOrBeamPosition.SAFE, group=group)
    yield from bps.wait(group)


def robot_unload(
    robot: Robot = robot,
    hutch_interlock: HutchInterlock = hutch_interlock,
) -> MsgGenerator[None]:
    hutch_status = yield from bps.rd(hutch_interlock.status)
    assert hutch_status == HUTCH_SAFE_FOR_OPERATIONS, (
        f"Hutch status was not 0, but instead {hutch_status}."
    )

    yield from bps.abs_set(robot, SAMPLE_LOCATION_EMPTY, wait=True)
