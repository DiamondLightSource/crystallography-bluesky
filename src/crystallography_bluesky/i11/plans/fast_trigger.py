import time
from enum import StrEnum
from typing import Callable

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
from bluesky.utils import MsgGenerator
from dodal.common import inject
from dodal.common.enums import OpenCloseUpper
from dodal.devices.beamlines.i11.dcm import DCM
from dodal.devices.beamlines.i11.diff_stages import (
    DiffractometerBase,
    DiffractometerStage,
)
from dodal.devices.beamlines.i11.fastcs_mythen import (
    FastCSMythen3,
    Mythen3DetectorState,
)
from dodal.devices.beamlines.i11.simple_panda import SimplePanda
from dodal.devices.fast_shutter import FastShutter
from dodal.devices.scaler_card import ScalerCard
from dodal.devices.synchrotron import Synchrotron
from dodal.devices.temperature_controller.mercury_itc import MercuryITC
from dodal.devices.tenma_psu import TenmaPSU
from dodal.log import LOGGER
from ophyd_async.core._detector import DetectorTrigger, TriggerInfo

mercury_itc = inject("mercury_itc")
fastcs_mythen3 = inject("fastcs_mythen3")
diff_stage = inject("diff_stage")
diff_base = inject("diff_base")
synchrotron = inject("synchrotron")
tenma_psu = inject("tenma_psu")
scaler2 = inject("scaler2")
panda = inject("bad_panda")
fast_shutter = inject("fast_shutter")
dcm = inject("dcm")


class ScanType(StrEnum):
    TIME_RESOLVED = "time_resolved"
    STEP_SCAN = "step_scan"


def scan_delta_with_mythen(
    exposure_time_per_point: float,
    delta_positions: list[float],
    time_between_frames: float = 20,
    mythen: FastCSMythen3 = fastcs_mythen3,
    diff_stage: DiffractometerStage = diff_stage,
    diff_base: DiffractometerBase = diff_base,
    synchrotron: Synchrotron = synchrotron,
    fast_shutter: FastShutter[OpenCloseUpper] = fast_shutter,
    dcm: DCM = dcm,
) -> MsgGenerator[None]:
    """
    Scan the delta stage with the Mythen detector.

    Ideally this would trigger the Mythen at each delta position. However, the
    Mythen currently does not support multiple external triggers. Instead the Mythen
    will be triggered with enough time between frames for us to move delta.


    Parameters
    ----------
    exposure_time_per_point : float
        Exposure time for each point in seconds.
    delta_positions : list[float]
        List of delta positions to scan.
    time_between_frames : float, optional
        Time between frames in seconds, by default 20.
    """
    mythen_trigger_info = TriggerInfo(
        collections_per_event=1,
        number_of_events=len(delta_positions),
        trigger=DetectorTrigger.INTERNAL,
        livetime=exposure_time_per_point,
        deadtime=time_between_frames,
    )

    detectors = [mythen]
    metadata = {
        "detectors": [detector.name for detector in detectors],
        "scan_type": ScanType.STEP_SCAN,
    }

    baseline_devices = [diff_stage, synchrotron, dcm.energy_in_keV, diff_base]
    LOGGER.info(f"Baseline devices: {baseline_devices}")

    yield from bps.mv(mythen.driver.bitdepth, 32)

    @bpp.stage_decorator([mythen])
    @bpp.baseline_decorator(baseline_devices)
    @bpp.run_decorator(md=metadata)
    def inner_run() -> MsgGenerator[None]:
        position = delta_positions[0]
        LOGGER.info(f"Moving to {position}")
        yield from bps.mv(diff_stage.delta, position)

        LOGGER.info("Opening shutter")
        yield from bps.stage(fast_shutter, wait=True)

        LOGGER.info("Preparing mythen")
        yield from bps.prepare(mythen, mythen_trigger_info, wait=True)

        yield from bps.declare_stream(*detectors, name="primary", collect=True)

        LOGGER.info("Kickoff mythen")
        yield from bps.kickoff_all(*detectors, wait=True)

        LOGGER.info("Reading delta")
        yield from bps.create(name="delta")
        yield from bps.read(diff_stage)
        yield from bps.save()

        LOGGER.info("Waiting for running")
        for _ in range(4):
            status = yield from bps.rd(mythen.driver.detector_status)

            if status == Mythen3DetectorState.RUNNING:
                LOGGER.info("First frame started")
                break
            yield from bps.sleep(1)

        for idx, position in enumerate(delta_positions[1:]):
            LOGGER.info(f"Waiting for frame {idx}")
            for _ in range(int(exposure_time_per_point) + 10):
                frames_written = yield from bps.rd(mythen.driver.frames_written)

                if frames_written > idx:
                    LOGGER.info(f"Frame {idx} written")
                    break
                yield from bps.sleep(1)

            LOGGER.info(f"Moving to {position}")
            yield from bps.mv(diff_stage.delta, position)

            LOGGER.info("Reading delta")
            yield from bps.create(name="delta")
            yield from bps.read(diff_stage)
            yield from bps.save()

        LOGGER.info("Completing Capture")
        yield from bps.complete_all(*detectors, wait=True)

        LOGGER.info("Collecting")
        yield from bps.collect(*detectors, return_payload=False, name="primary")

        LOGGER.info("Closing shutter")
        yield from bps.unstage(fast_shutter, wait=True)

    yield from inner_run()


def _generic_fast_trigger_mythen(
    number_of_frames: int,
    exposure_time: float,
    time_between_frames: float = 0,
    do_whilst_collect: Callable[[], MsgGenerator[None]] | None = None,
    mythen: FastCSMythen3 = fastcs_mythen3,
    diff_stage: DiffractometerStage = diff_stage,
    diff_base: DiffractometerBase = diff_base,
    synchrotron: Synchrotron = synchrotron,
    tenma_psu: TenmaPSU = tenma_psu,
    scaler2: ScalerCard = scaler2,
    panda: SimplePanda = panda,
    fast_shutter: FastShutter[OpenCloseUpper] = fast_shutter,
    dcm: DCM = dcm,
) -> MsgGenerator[None]:
    if do_whilst_collect is None:
        do_whilst_collect = bps.null

    mythen_trigger_info = TriggerInfo(
        collections_per_event=1,
        number_of_events=number_of_frames,
        trigger=DetectorTrigger.EXTERNAL_EDGE,
        livetime=exposure_time,
    )

    detectors = [mythen]
    metadata = {
        "detectors": [detector.name for detector in detectors],
        "scan_type": ScanType.TIME_RESOLVED,
    }

    baseline_devices = [
        diff_stage,
        synchrotron,
        tenma_psu,
        dcm.energy_in_keV,
        diff_base,
    ]
    LOGGER.info(f"Baseline devices: {baseline_devices}")

    if time_between_frames != 0:
        yield from bps.mv(mythen.driver.period, time_between_frames + exposure_time)
    else:
        yield from bps.mv(mythen.driver.period, 0)

    yield from bps.mv(scaler2, exposure_time)
    yield from bps.mv(mythen.driver.bitdepth, 32)
    yield from bps.mv(panda._trigger, False)

    @bpp.stage_decorator([mythen, fast_shutter])
    @bpp.baseline_decorator(baseline_devices)
    @bpp.run_decorator(md=metadata)
    def inner_run() -> MsgGenerator[None]:

        LOGGER.info("Preparing mythen")
        yield from bps.prepare(mythen, mythen_trigger_info, wait=True)

        yield from bps.declare_stream(*detectors, name="primary", collect=True)

        LOGGER.info("Kickoff mythen")
        yield from bps.kickoff_all(*detectors, wait=True)

        LOGGER.info("Reading i0/ie")

        yield from bps.trigger(scaler2)
        yield from bps.create(name="scaler2")
        yield from bps.read(scaler2)
        yield from bps.save()

        LOGGER.info("Triggering panda")
        yield from bps.mv(panda._trigger, True)

        yield from bps.create(name="panda")
        yield from bps.read(panda)
        yield from bps.save()

        yield from do_whilst_collect()

        LOGGER.info("Completing Capture")
        yield from bps.complete_all(*detectors, wait=True)

        LOGGER.info("Collecting")
        yield from bps.collect(*detectors, return_payload=False, name="primary")

    yield from inner_run()


def psu_ramp_with_fast_trigger(
    psu_currents: list[float],
    wait_between_psu_steps_s: float,
    exposure_time: float,
    time_between_frames: float,
    mercury_itc: MercuryITC = mercury_itc,
    mythen: FastCSMythen3 = fastcs_mythen3,
    diff_stage: DiffractometerStage = diff_stage,
    diff_base: DiffractometerBase = diff_base,
    synchrotron: Synchrotron = synchrotron,
    tenma_psu: TenmaPSU = tenma_psu,
    scaler2: ScalerCard = scaler2,
    panda: SimplePanda = panda,
    fast_shutter: FastShutter[OpenCloseUpper] = fast_shutter,
    dcm: DCM = dcm,
) -> MsgGenerator[None]:

    def _while_collect() -> MsgGenerator[None]:
        yield from bps.create(name="mercury")
        yield from bps.read(mercury_itc)
        yield from bps.read(panda)
        yield from bps.save()

        yield from bps.mv(tenma_psu.output, True)

        for psu_current in psu_currents:
            LOGGER.info(f"Setting PSU current to {psu_current}")
            yield from bps.mv(tenma_psu.current_sp, psu_current)
            time_for_next_ramp = time.monotonic() + wait_between_psu_steps_s

            LOGGER.info("Setting current, reading temp while we wait")
            while time.monotonic() < time_for_next_ramp:
                yield from bps.create(name="mercury")
                yield from bps.read(mercury_itc)
                yield from bps.read(panda)
                yield from bps.save()

    full_collection_time = len(psu_currents) * wait_between_psu_steps_s
    number_of_frames = full_collection_time / (exposure_time + time_between_frames)

    yield from _generic_fast_trigger_mythen(
        int(number_of_frames),
        exposure_time,
        time_between_frames,
        _while_collect,
        mythen,
        diff_stage,
        diff_base,
        synchrotron,
        tenma_psu,
        scaler2,
        panda,
        fast_shutter,
        dcm,
    )


def fast_trigger_mythen(
    number_of_frames: int,
    exposure_time: float,
    mercury_itc: MercuryITC = mercury_itc,
    mythen: FastCSMythen3 = fastcs_mythen3,
    diff_stage: DiffractometerStage = diff_stage,
    diff_base: DiffractometerBase = diff_base,
    synchrotron: Synchrotron = synchrotron,
    tenma_psu: TenmaPSU = tenma_psu,
    scaler2: ScalerCard = scaler2,
    panda: SimplePanda = panda,
    fast_shutter: FastShutter[OpenCloseUpper] = fast_shutter,
    dcm: DCM = dcm,
) -> MsgGenerator[None]:

    def _while_collect() -> MsgGenerator[None]:
        LOGGER.info("Reading mercury")
        timeout = time.monotonic() + number_of_frames * exposure_time + 5
        while time.monotonic() < timeout:
            yield from bps.create(name="mercury")
            yield from bps.read(mercury_itc)
            yield from bps.read(panda)
            yield from bps.save()

            mythen_status = yield from bps.rd(mythen.driver.detector_status)
            if mythen_status == Mythen3DetectorState.IDLE:
                LOGGER.info("Mythen finished")
                break

    yield from _generic_fast_trigger_mythen(
        number_of_frames,
        exposure_time,
        0,
        _while_collect,
        mythen,
        diff_stage,
        diff_base,
        synchrotron,
        tenma_psu,
        scaler2,
        panda,
        fast_shutter,
        dcm,
    )
