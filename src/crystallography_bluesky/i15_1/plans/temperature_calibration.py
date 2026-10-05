from daq_config_server.models.i15_1.standards_puck import (
    STANDARD_CAPILLARY,
    STANDARD_SAMPLE,
    StandardsPin,
    StandardsPuck,
)
from dodal.common import inject
from dodal.common.beamlines.beamline_utils import get_config_client
from dodal.devices.beamlines.i15_1.blower import Blower
from dodal.devices.beamlines.i15_1.cobra import Cobra
from dodal.devices.beamlines.i15_1.robot import Robot
from dodal.devices.interlocks import IntPLCInterlock, PSSInterlock

from crystallography_bluesky.i15_1.plans import (
    blower_collection,
    centre_sample,
    robot_load,
    robot_unload,
)
from crystallography_bluesky.i15_1.plans.generic_collection import (
    AuxiliaryScanType,
    GenericCollectionDevices,
)

STANDARDS_PUCK_CONFIG_PATH = (
    "/dls_sw/i15-1/software/daq_configuration/standards_puck.json"
)

devices = inject("")
robot = inject("robot")
hutch_interlock = inject("hutch_interlock")
gonio_interlock = inject("gonio_interlock")
hexapod = inject("hexapod")
blower = inject("blower")
cobra = inject("cobra")


def temperature_calibration(
    capillary: STANDARD_CAPILLARY,
    contents: STANDARD_SAMPLE,
    time_per_collection: float,
    exposure_time_per_frame: float,
    temperatures_celsius: list[float],
    ramp_rate_c_per_min: float,
    settle_time: float,
    generic_collection_devices: GenericCollectionDevices = devices,
    robot: Robot = robot,
    hutch_interlock: PSSInterlock = hutch_interlock,
    gonio_interlock: IntPLCInterlock = gonio_interlock,
    hexapod=hexapod,
    blower: Blower = blower,
    cobra: Cobra = cobra,
):
    config_client = get_config_client()
    standards_puck = config_client.get_file_contents(
        STANDARDS_PUCK_CONFIG_PATH, desired_return_type=StandardsPuck
    )
    pin_position = standards_puck.get_position_of_pin(
        StandardsPin(capillary=capillary, contents=contents)
    )

    yield from robot_load(
        puck=1,
        position=pin_position,
        robot=robot,
        hutch_interlock=hutch_interlock,
        gonio_interlock=gonio_interlock,
        hexapod=hexapod,
        blower=blower,
        cobra=cobra,
    )
    yield from centre_sample(-20, 5, 100, 0.1, generic_collection_devices, hexapod)
    yield from blower_collection(
        time_per_collection,
        exposure_time_per_frame,
        temperatures_celsius,
        ramp_rate_c_per_min,
        settle_time,
        AuxiliaryScanType.STANDARD_SAMPLE,
        generic_collection_devices,
        blower,
    )
    yield from robot_unload()
