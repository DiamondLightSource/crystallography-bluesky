from bluesky import plan_stubs as bps
from bluesky.utils import MsgGenerator
from daq_config_server.models.i15_1.xpdf_parameters import RobotLoadDevicesConfiguration
from dodal.common import inject
from dodal.common.beamlines.beamline_utils import get_config_client
from dodal.devices.beamlines.i15_1.robot import Robot, SampleLocation
from ophyd_async.epics.motor import Motor

XPDF_PARAMETERS_FILEPATH = "/dls_sw/i15-1/software/gda_var/xpdfLocalParameters.xml"


def robot_load(
    puck: int,
    position: int,
    robot: Robot = inject("robot"),
    blower: Motor = inject("blower_y"),
) -> MsgGenerator[None]:
    yield from move_blower_to_safe_position(blower)
    sample = SampleLocation(puck, position)
    yield from bps.abs_set(robot, sample, wait=True)


def move_blower_to_safe_position(blower: Motor):
    config_client = get_config_client()
    blower_config = config_client.get_file_contents(
        XPDF_PARAMETERS_FILEPATH,
        desired_return_type=RobotLoadDevicesConfiguration,
        force_parser=RobotLoadDevicesConfiguration.from_xpdf_parameters,
    ).blower
    yield from bps.abs_set(blower, blower_config.safe_position, wait=True)
