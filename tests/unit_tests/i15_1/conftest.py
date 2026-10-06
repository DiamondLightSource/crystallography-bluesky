from pathlib import Path
from typing import Literal
from unittest.mock import MagicMock, patch

import pytest
from bluesky import RunEngine
from daq_config_server.client import ConfigClient
from daq_config_server.models.i15_1.collection_specification import (
    CollectionSpecification,
    SpecificationPerPosition,
)
from daq_config_server.models.i15_1.standards_puck import StandardsPin, StandardsPuck
from daq_config_server.models.i15_1.temperature_calibration import (
    TemperatureCalibration,
)
from daq_config_server.models.i15_1.xpdf_parameters import (
    TemperatureControllerParams,
    TemperatureControllersConfig,
)
from daq_config_server.testing import MockServerResponse, PathToMockDataDict
from dodal.beamlines.i15_1 import (
    BLOWER_TEMPERATURE_CALIBRATION_FILEPATH,
    XPDF_PARAMETERS_FILEPATH,
)
from dodal.devices.beamlines.i15_1.attenuators import FastAttenuator, SlowAttenuator
from dodal.devices.beamlines.i15_1.beam_health import BeamHealth
from dodal.devices.beamlines.i15_1.blower import Blower, CalibratedBlower
from dodal.devices.beamlines.i15_1.cobra import Cobra
from dodal.devices.beamlines.i15_1.hexapod import Hexapod
from dodal.devices.beamlines.i15_1.laue import LaueMonochrometer
from dodal.devices.beamlines.i15_1.robot import Robot
from dodal.devices.interlocks import IntPLCInterlock, PSSInterlock
from dodal.devices.synchrotron import Synchrotron
from dodal.devices.tetramm import SummingTetrammDetector
from dodal.devices.zebra.zebra import Zebra, ZebraMapping
from dodal.devices.zebra.zebra_constants_mapping import ZebraOutputs
from dodal.devices.zebra.zebra_controlled_shutter import ZebraFastShutter
from ophyd_async.core import (
    StaticFilenameProvider,
    StaticPathProvider,
    init_devices,
    set_mock_value,
)
from ophyd_async.epics.motor import Motor
from ophyd_async.fastcs.eiger import EigerDetector

from crystallography_bluesky.i15_1.plans.generic_collection import (
    GenericCollectionDevices,
)
from crystallography_bluesky.i15_1.plans.room_temperature_collection import (
    COLLECTION_SPEC_FILEPATH,
)
from crystallography_bluesky.i15_1.plans.temperature_calibration import (
    STANDARDS_PUCK_CONFIG_PATH,
)


@pytest.fixture
def run_engine():
    return RunEngine()


@pytest.fixture
def path_provider() -> StaticPathProvider:
    return StaticPathProvider(StaticFilenameProvider(""), Path(""))


@pytest.fixture
async def i0(path_provider: StaticPathProvider) -> SummingTetrammDetector:
    async with init_devices(mock=True):
        i0 = SummingTetrammDetector(
            "",
            path_provider,
            name="i0",
        )
    return i0


@pytest.fixture
async def zebra() -> Zebra:
    async with init_devices(mock=True):
        zebra = Zebra(
            ZebraMapping(outputs=ZebraOutputs(LVDS_EIGER=3, TTL_I0=2)),
            "",
            "zebra",
        )
    return zebra


@pytest.fixture
async def robot() -> Robot:
    async with init_devices(mock=True):
        robot = Robot("", "")

    return robot


@pytest.fixture
async def tth() -> Motor:
    async with init_devices(mock=True):
        tth = Motor("", "")

    return tth


@pytest.fixture
async def slow_attenuator() -> SlowAttenuator:
    async with init_devices(mock=True):
        slow_attenuator = SlowAttenuator("", "")

    return slow_attenuator


@pytest.fixture
async def fast_attenuator() -> FastAttenuator:
    async with init_devices(mock=True):
        fast_attenuator = FastAttenuator("", "")

    return fast_attenuator


@pytest.fixture
async def eiger(path_provider: StaticPathProvider) -> EigerDetector:
    async with init_devices(mock=True):
        eiger = EigerDetector(
            name="fastcs-eiger",
            prefix="",
            path_provider=path_provider,
        )
    return eiger


@pytest.fixture
async def fast_shutter() -> ZebraFastShutter:
    async with init_devices(mock=True):
        zebra_fast_shutter = ZebraFastShutter("", "", "fast_shutter")
    return zebra_fast_shutter


@pytest.fixture
async def hexapod() -> Hexapod:
    async with init_devices(mock=True):
        hexapod = Hexapod("", "")
    return hexapod


@pytest.fixture
async def xtal() -> LaueMonochrometer:
    async with init_devices(mock=True):
        xtal = LaueMonochrometer("", ConfigClient.from_url(""), "")
    return xtal


@pytest.fixture
async def synchrotron() -> Synchrotron:
    async with init_devices(mock=True):
        synchrotron = Synchrotron()
    return synchrotron


@pytest.fixture
async def beam_health() -> BeamHealth:
    async with init_devices(mock=True):
        beam_health = BeamHealth("")
    return beam_health


@pytest.fixture
async def common_collection_devices(
    eiger: EigerDetector,
    i0: SummingTetrammDetector,
    zebra: Zebra,
    robot: Robot,
    tth: Motor,
    fast_shutter: ZebraFastShutter,
    xtal: LaueMonochrometer,
    slow_attenuator: SlowAttenuator,
    fast_attenuator: FastAttenuator,
    synchrotron: Synchrotron,
) -> GenericCollectionDevices:
    return GenericCollectionDevices(
        eiger,
        i0,
        zebra,
        robot,
        tth,
        fast_shutter,
        xtal,
        fast_attenuator,
        slow_attenuator,
        synchrotron,
    )


@pytest.fixture
async def blower(mock_config_client: ConfigClient) -> Blower:
    """Blower device for testing."""
    async with init_devices(mock=True):
        blower = Blower("", "", "", mock_config_client, XPDF_PARAMETERS_FILEPATH)
    return blower


@pytest.fixture
async def calibrated_blower(mock_config_client: ConfigClient) -> Blower:
    """Blower device for testing."""
    async with init_devices(mock=True):
        blower = CalibratedBlower(
            "",
            "",
            "",
            mock_config_client,
            XPDF_PARAMETERS_FILEPATH,
            BLOWER_TEMPERATURE_CALIBRATION_FILEPATH,
        )
    return blower


@pytest.fixture
async def cobra(mock_config_client: ConfigClient) -> Cobra:
    async with init_devices(mock=True):
        cobra = Cobra("", mock_config_client, XPDF_PARAMETERS_FILEPATH)
    return cobra


@pytest.fixture
async def hutch_interlock() -> PSSInterlock:
    async with init_devices(mock=True):
        hutch_interlock = PSSInterlock("", "")
    set_mock_value(hutch_interlock.status, 0)
    return hutch_interlock


@pytest.fixture
async def gonio_interlock() -> IntPLCInterlock:
    async with init_devices(mock=True):
        gonio_interlock = IntPLCInterlock("", "")
    set_mock_value(gonio_interlock.status, 65535)
    return gonio_interlock


@pytest.fixture
def positions_to_spec() -> dict[int, tuple[float, float, Literal["IN", "OUT"]]]:
    return {
        10: (0.05, 0.001, "IN"),
        20: (0.05, 0.01, "IN"),
        30: (0.1, 0.1, "IN"),
        40: (0.2, 10, "OUT"),
        50: (0.3, 50, "OUT"),
        60: (0.3, 100, "OUT"),
    }


@pytest.fixture
def standards_puck():
    return StandardsPuck(
        position_on_table=1,
        pins={
            1: StandardsPin(capillary="metal", contents=None),
            2: StandardsPin(capillary="bs1.0", contents="Silicon"),
            3: StandardsPin(capillary="fq1.0", contents="Silicon"),
            4: StandardsPin(capillary="bs1.5", contents="Silicon"),
            5: None,
            6: StandardsPin(capillary="bs2.0", contents="Silicon"),
            7: None,
            8: None,
            9: StandardsPin(capillary="bs1.0", contents="Si/Al2O3"),
            10: StandardsPin(capillary="fq1.0", contents="Si/Al2O3"),
            11: StandardsPin(capillary="fq1.5", contents="Si/Al2O3"),
            12: StandardsPin(capillary="fq2.0", contents="Si/Al2O3"),
            13: StandardsPin(capillary="bs1.0", contents="Pb"),
            14: StandardsPin(capillary="bs1.0", contents="LaB6 660b"),
            15: StandardsPin(capillary="bs1.0", contents=None),
            16: StandardsPin(capillary="fq1.0", contents=None),
            17: StandardsPin(capillary="bs1.5", contents=None),
            18: StandardsPin(capillary="fq1.5", contents=None),
            19: StandardsPin(capillary="bs2.0", contents=None),
            20: StandardsPin(capillary="fq2.0", contents=None),
            21: StandardsPin(capillary="bs1.0", contents="Ga/In"),
            22: StandardsPin(capillary="bs1.0", contents="Tungsten/Boron mix"),
        },
    )


@pytest.fixture
def temperature_controller_params():
    return TemperatureControllersConfig(
        blower=TemperatureControllerParams(
            beam_position=40.7,
            safe_position=6.0,
            settle_time=0,
            tolerance=5.0,
            units="C",
            ramp_units="/min",
            use_calibration=True,
            use_fast_cool=None,
            calibration_file="blower_cal_10_03_2026.txt",
        ),
        cobra=TemperatureControllerParams(
            beam_position=400.5,
            safe_position=5.0,
            settle_time=600,
            tolerance=5.0,
            units="K",
            ramp_units="/h",
            use_calibration=True,
            use_fast_cool=True,
            calibration_file="cobra_calibration_2025-09-11.txt",
        ),
        cryostream=TemperatureControllerParams(
            beam_position=469.9,
            safe_position=0,
            ramp_units="/h",
            units="K",
            tolerance=0.5,
            settle_time=600,
            calibration_file="cryostream_cal_2025-01-23.txt",
            use_calibration=True,
        ),
    )


@pytest.fixture
def blower_calibration():
    return TemperatureCalibration(
        rows=[
            [50.0, 0.62034],
            [100.0, 16.89903],
            [150.0, 26.49641],
            [200.0, 33.91664],
            [250.0, 47.85712],
            [300.0, 62.41245],
            [350.0, 80.13215],
            [400.0, 96.91991],
            [450.0, 115.6384],
            [500.0, 135.89034],
            [550.0, 155.75917],
        ]
    )


@pytest.fixture
def mock_config(
    positions_to_spec: dict[int, tuple[float, float, Literal["IN", "OUT"]]],
    standards_puck: StandardsPuck,
    temperature_controller_params: TemperatureControllersConfig,
    blower_calibration: TemperatureCalibration,
) -> PathToMockDataDict:
    return {
        COLLECTION_SPEC_FILEPATH: CollectionSpecification(
            tth_angle_to_specification={
                pos: SpecificationPerPosition(
                    exposure_time=spec[0],
                    slow_attenuator_transmission=spec[1],
                    fast_attenuator_position=spec[2],
                )
                for pos, spec in positions_to_spec.items()
            }
        ),
        STANDARDS_PUCK_CONFIG_PATH: standards_puck,
        XPDF_PARAMETERS_FILEPATH: temperature_controller_params,
        BLOWER_TEMPERATURE_CALIBRATION_FILEPATH: blower_calibration,
    }


@pytest.fixture(autouse=True)
def mock_config_client(mock_config: PathToMockDataDict):
    client = ConfigClient(server_response=MockServerResponse(mock_config))
    client.get_file_contents = MagicMock(wraps=client.get_file_contents)
    with (
        patch(
            "crystallography_bluesky.i15_1.plans.room_temperature_collection.get_config_client",
            return_value=client,
        ),
        patch(
            "crystallography_bluesky.i15_1.plans.temperature_calibration.get_config_client",
            return_value=client,
        ),
    ):
        yield client
