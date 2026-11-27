from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

import pytest
from bluesky import RunEngine
from dodal.common.enums import OpenCloseUpper
from dodal.devices.beamlines.i11.dcm import DCM
from dodal.devices.beamlines.i11.diff_stages import (
    DiffractometerBase,
    DiffractometerStage,
)
from dodal.devices.beamlines.i11.fastcs_mythen import FastCSMythen3
from dodal.devices.beamlines.i11.simple_panda import SimplePanda
from dodal.devices.fast_shutter import FastShutter
from dodal.devices.scaler_card import ScalerCard, ScalerCardController
from dodal.devices.synchrotron import Synchrotron
from dodal.devices.temperature_controller.mercury_itc import MercuryITC
from dodal.devices.tenma_psu import TenmaPSU
from ophyd_async.core import (
    DeviceMap,
    StaticFilenameProvider,
    StaticPathProvider,
    init_devices,
)
from ophyd_async.epics.core import epics_signal_r


class FastTriggerArguments(TypedDict):
    mythen: FastCSMythen3
    diff_stage: DiffractometerStage
    diff_base: DiffractometerBase
    synchrotron: Synchrotron
    tenma_psu: TenmaPSU
    scaler2: ScalerCard[DeviceMap]
    panda: SimplePanda
    fast_shutter: FastShutter[OpenCloseUpper]
    dcm: DCM


@dataclass
class FastTriggerDevices:
    mythen: FastCSMythen3
    diff_stage: DiffractometerStage
    diff_base: DiffractometerBase
    synchrotron: Synchrotron
    tenma_psu: TenmaPSU
    scaler2: ScalerCard[DeviceMap]
    panda: SimplePanda
    fast_shutter: FastShutter[OpenCloseUpper]
    dcm: DCM
    mercury_itc: MercuryITC

    def common(self) -> FastTriggerArguments:
        return {
            "mythen": self.mythen,
            "diff_stage": self.diff_stage,
            "diff_base": self.diff_base,
            "synchrotron": self.synchrotron,
            "tenma_psu": self.tenma_psu,
            "scaler2": self.scaler2,
            "panda": self.panda,
            "fast_shutter": self.fast_shutter,
            "dcm": self.dcm,
        }


@pytest.fixture
def run_engine() -> RunEngine:
    return RunEngine()


@pytest.fixture
async def fast_trigger_devices(tmp_path: Path) -> FastTriggerDevices:
    path_provider = StaticPathProvider(StaticFilenameProvider("mythen"), tmp_path)
    async with init_devices(mock=True):
        mythen = FastCSMythen3("MYTHEN:", path_provider)
        diff_stage = DiffractometerStage("DIFF:")
        diff_base = DiffractometerBase("BASE:")
        synchrotron = Synchrotron()
        tenma_psu = TenmaPSU("PSU:")
        scaler_controller = ScalerCardController("SCALER", ".CNT", ".TP")
        scaler2 = ScalerCard(
            DeviceMap(
                {
                    "i0": epics_signal_r(float, "SCALER.S17"),
                    "ie": epics_signal_r(float, "SCALER.S18"),
                }
            ),
            scaler_controller,
        )
        panda = SimplePanda("PANDA:")
        fast_shutter = FastShutter[OpenCloseUpper](
            "SHUTTER", OpenCloseUpper.OPEN, OpenCloseUpper.CLOSE
        )
        dcm = DCM("DCM:", "XTAL:")
        mercury_itc = MercuryITC("MERCURY:")
    return FastTriggerDevices(
        mythen,
        diff_stage,
        diff_base,
        synchrotron,
        tenma_psu,
        scaler2,
        panda,
        fast_shutter,
        dcm,
        mercury_itc,
    )
