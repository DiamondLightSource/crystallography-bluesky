from types import SimpleNamespace
from unittest.mock import Mock, call, patch

import bluesky.plan_stubs as bps
import pytest
from bluesky import RunEngine
from bluesky.simulators import RunEngineSimulator, assert_message_and_return_remaining
from bluesky.utils import MsgGenerator
from dodal.devices.beamlines.i11.fastcs_mythen import Mythen3DetectorState
from ophyd_async.core import (
    DetectorTrigger,
    callback_on_mock_put,
    get_mock_put,
    set_mock_value,
)

from crystallography_bluesky.i11.plans.fast_trigger import (
    ScanType,
    _generic_fast_trigger_mythen,
    fast_trigger_mythen,
    psu_ramp_with_fast_trigger,
    scan_delta_with_mythen,
)

from .conftest import FastTriggerDevices


def _step_scan(devices: FastTriggerDevices):
    return scan_delta_with_mythen(
        0.1,
        [1.0, 2.0],
        mythen=devices.mythen,
        diff_stage=devices.diff_stage,
        diff_base=devices.diff_base,
        synchrotron=devices.synchrotron,
        fast_shutter=devices.fast_shutter,
        dcm=devices.dcm,
        panda=devices.panda,
    )


def test_step_scan_moves_and_triggers_each_position(
    fast_trigger_devices: FastTriggerDevices,
):
    devices = fast_trigger_devices
    simulator = RunEngineSimulator()
    simulator.add_read_handler_for(
        devices.mythen.driver.detector_status, Mythen3DetectorState.RUNNING
    )
    frames = iter([1, 2])
    simulator.add_handler(
        "read",
        lambda msg: {msg.obj.name: {"value": next(frames), "timestamp": 0}},
        msg_filter=devices.mythen.driver.frames_written.name,
    )
    msgs = simulator.simulate_plan(_step_scan(devices))

    msgs = assert_message_and_return_remaining(
        msgs,
        lambda msg: (
            msg.command == "set"
            and msg.obj is devices.mythen.driver.bitdepth
            and msg.args == (32,)
        ),
    )
    msgs = assert_message_and_return_remaining(
        msgs,
        lambda msg: (
            msg.command == "set"
            and msg.obj is devices.panda.pulse_width
            and msg.args == (0.01,)
        ),
    )
    msgs = assert_message_and_return_remaining(
        msgs,
        lambda msg: (
            msg.command == "open_run"
            and msg.kwargs["scan_type"] == ScanType.STEP_SCAN
            and msg.kwargs["detectors"] == [devices.mythen.name]
        ),
    )
    msgs = assert_message_and_return_remaining(
        msgs, lambda msg: msg.command == "stage" and msg.obj is devices.fast_shutter
    )
    msgs = assert_message_and_return_remaining(
        msgs,
        lambda msg: (
            msg.command == "prepare"
            and msg.obj is devices.mythen
            and msg.args[0].number_of_events == 2
            and msg.args[0].livetime == 0.1
            and msg.args[0].trigger == DetectorTrigger.EXTERNAL_EDGE
        ),
    )
    msgs = assert_message_and_return_remaining(
        msgs, lambda msg: msg.command == "kickoff" and msg.obj is devices.mythen
    )
    for position in [1.0, 2.0]:
        msgs = assert_message_and_return_remaining(
            msgs,
            lambda msg, position=position: (
                msg.command == "set"
                and msg.obj is devices.diff_stage.delta
                and msg.args == (position,)
            ),
        )
        msgs = assert_message_and_return_remaining(
            msgs, lambda msg: msg.command == "read" and msg.obj is devices.diff_stage
        )
        msgs = assert_message_and_return_remaining(
            msgs,
            lambda msg: (
                msg.command == "set"
                and msg.obj is devices.panda._trigger
                and msg.args == (True,)
            ),
        )
        msgs = assert_message_and_return_remaining(
            msgs,
            lambda msg: (
                msg.command == "read"
                and msg.obj is devices.mythen.driver.frames_written
            ),
        )
        msgs = assert_message_and_return_remaining(
            msgs,
            lambda msg: (
                msg.command == "set"
                and msg.obj is devices.panda._trigger
                and msg.args == (False,)
            ),
        )
    msgs = assert_message_and_return_remaining(
        msgs, lambda msg: msg.command == "complete" and msg.obj is devices.mythen
    )
    msgs = assert_message_and_return_remaining(
        msgs, lambda msg: msg.command == "collect" and msg.obj is devices.mythen
    )
    assert_message_and_return_remaining(
        msgs, lambda msg: msg.command == "unstage" and msg.obj is devices.fast_shutter
    )


def test_step_scan_raises_when_frame_is_not_written(
    fast_trigger_devices: FastTriggerDevices,
):
    devices = fast_trigger_devices
    simulator = RunEngineSimulator()
    simulator.add_read_handler_for(
        devices.mythen.driver.detector_status, Mythen3DetectorState.RUNNING
    )
    simulator.add_read_handler_for(devices.mythen.driver.frames_written, 0)
    with pytest.raises(
        Exception, match="Frame 0 has not been written in sufficient time"
    ):
        simulator.simulate_plan(_step_scan(devices))


@pytest.mark.parametrize("gap, expected_period", [(0, 0), (0.3, 0.5)])
def test_generic_fast_trigger_configures_and_collects(
    fast_trigger_devices: FastTriggerDevices, gap: float, expected_period: float
):
    devices = fast_trigger_devices
    simulator = RunEngineSimulator()
    msgs = simulator.simulate_plan(
        _generic_fast_trigger_mythen(4, 0.2, gap, **devices.common())
    )
    msgs = assert_message_and_return_remaining(
        msgs,
        lambda msg: (
            msg.command == "set"
            and msg.obj is devices.mythen.driver.period
            and msg.args[0] == pytest.approx(expected_period)
        ),
    )
    msgs = assert_message_and_return_remaining(
        msgs,
        lambda msg: (
            msg.command == "set" and msg.obj is devices.scaler2 and msg.args == (0.2,)
        ),
    )
    msgs = assert_message_and_return_remaining(
        msgs,
        lambda msg: (
            msg.command == "open_run"
            and msg.kwargs["scan_type"] == ScanType.TIME_RESOLVED
            and msg.kwargs["detectors"] == [devices.mythen.name]
        ),
    )
    msgs = assert_message_and_return_remaining(
        msgs,
        lambda msg: (
            msg.command == "prepare"
            and msg.obj is devices.mythen
            and msg.args[0].number_of_events == 4
            and msg.args[0].livetime == 0.2
            and msg.args[0].trigger == DetectorTrigger.INTERNAL
        ),
    )
    msgs = assert_message_and_return_remaining(
        msgs, lambda msg: msg.command == "kickoff" and msg.obj is devices.mythen
    )
    msgs = assert_message_and_return_remaining(
        msgs, lambda msg: msg.command == "trigger" and msg.obj is devices.scaler2
    )
    msgs = assert_message_and_return_remaining(
        msgs, lambda msg: msg.command == "read" and msg.obj is devices.scaler2
    )
    msgs = assert_message_and_return_remaining(
        msgs,
        lambda msg: (
            msg.command == "set"
            and msg.obj is devices.panda._trigger
            and msg.args == (True,)
        ),
    )
    msgs = assert_message_and_return_remaining(
        msgs, lambda msg: msg.command == "read" and msg.obj is devices.panda
    )
    msgs = assert_message_and_return_remaining(
        msgs, lambda msg: msg.command == "complete" and msg.obj is devices.mythen
    )
    assert_message_and_return_remaining(
        msgs, lambda msg: msg.command == "collect" and msg.obj is devices.mythen
    )


def test_generic_fast_trigger_runs_callback_before_completion(
    fast_trigger_devices: FastTriggerDevices,
):
    devices = fast_trigger_devices

    def while_collect() -> MsgGenerator[None]:
        yield from bps.mv(devices.tenma_psu.current_sp, 1.5)

    msgs = RunEngineSimulator().simulate_plan(
        _generic_fast_trigger_mythen(
            3, 0.1, do_whilst_collect=while_collect, **devices.common()
        )
    )
    msgs = assert_message_and_return_remaining(
        msgs,
        lambda msg: (
            msg.command == "set"
            and msg.obj is devices.panda._trigger
            and msg.args == (True,)
        ),
    )
    msgs = assert_message_and_return_remaining(
        msgs,
        lambda msg: (
            msg.command == "set"
            and msg.obj is devices.tenma_psu.current_sp
            and msg.args == (1.5,)
        ),
    )
    assert_message_and_return_remaining(
        msgs, lambda msg: msg.command == "complete" and msg.obj is devices.mythen
    )


def test_fast_trigger_reads_mercury_until_mythen_is_idle(
    fast_trigger_devices: FastTriggerDevices,
):
    devices = fast_trigger_devices
    simulator = RunEngineSimulator()
    states = iter([Mythen3DetectorState.RUNNING, Mythen3DetectorState.IDLE])
    simulator.add_handler(
        "read",
        lambda msg: {msg.obj.name: {"value": next(states), "timestamp": 0}},
        msg_filter=devices.mythen.driver.detector_status.name,
    )
    msgs = simulator.simulate_plan(
        fast_trigger_mythen(4, 0.1, mercury_itc=devices.mercury_itc, **devices.common())
    )
    reads = [msg.obj for msg in msgs if msg.command == "read"]
    assert reads.count(devices.mercury_itc) == 2
    assert reads.count(devices.mythen.driver.detector_status) == 2
    prepare = next(
        msg for msg in msgs if msg.command == "prepare" and msg.obj is devices.mythen
    )
    assert prepare.args[0].number_of_events == 4
    assert prepare.args[0].livetime == 0.1


def test_psu_ramp_sets_currents_and_reads_temperature(
    fast_trigger_devices: FastTriggerDevices,
):
    devices = fast_trigger_devices
    clock = SimpleNamespace(monotonic=Mock(side_effect=[0, 0, 2, 2, 2, 4]))
    with patch("crystallography_bluesky.i11.plans.fast_trigger.time", clock):
        msgs = RunEngineSimulator().simulate_plan(
            psu_ramp_with_fast_trigger(
                [1.0, 2.0],
                1.0,
                0.2,
                0.3,
                mercury_itc=devices.mercury_itc,
                **devices.common(),
            )
        )
    prepare = next(
        msg for msg in msgs if msg.command == "prepare" and msg.obj is devices.mythen
    )
    assert prepare.args[0].number_of_events == 4
    assert prepare.args[0].livetime == 0.2
    assert [
        msg.args[0]
        for msg in msgs
        if msg.command == "set" and msg.obj is devices.tenma_psu.current_sp
    ] == [1.0, 2.0]
    assert [
        msg
        for msg in msgs
        if msg.command == "set"
        and msg.obj is devices.tenma_psu.output
        and msg.args == (True,)
    ]
    assert (
        len(
            [
                msg
                for msg in msgs
                if msg.command == "read" and msg.obj is devices.mercury_itc
            ]
        )
        == 3
    )


def test_step_scan_with_run_engine(
    run_engine: RunEngine, fast_trigger_devices: FastTriggerDevices
):
    devices = fast_trigger_devices
    delta_positions = [1.0, 2.0]

    async def inc_frames_written(value: bool, *_, **__):
        if value:
            current_frames = await devices.mythen.driver.frames_written.get_value()
            new_frames = current_frames + 1
            set_mock_value(devices.mythen.driver.frames_written, new_frames + 1)
            if new_frames >= len(delta_positions):
                set_mock_value(
                    devices.mythen.driver.detector_status, Mythen3DetectorState.IDLE
                )

    callback_on_mock_put(
        devices.panda._trigger,
        inc_frames_written,
    )
    set_mock_value(devices.mythen.driver.detector_status, Mythen3DetectorState.RUNNING)
    run_engine(
        scan_delta_with_mythen(
            0.1,
            delta_positions,
            mythen=devices.mythen,
            diff_stage=devices.diff_stage,
            diff_base=devices.diff_base,
            synchrotron=devices.synchrotron,
            fast_shutter=devices.fast_shutter,
            dcm=devices.dcm,
            panda=devices.panda,
        )
    )
    get_mock_put(devices.panda._trigger).assert_has_calls(
        [call(False), call(True), call(False), call(True), call(False)]
    )
    get_mock_put(devices.fast_shutter.shutter_state).assert_has_calls(
        [call(devices.fast_shutter.open_state), call(devices.fast_shutter.close_state)]
    )


def _do_fast_collection_on_trigger(devices: FastTriggerDevices, number_of_frames: int):
    async def do_full_collection(value: bool, *_, **__):
        if value:
            set_mock_value(devices.mythen.driver.frames_written, number_of_frames)
            set_mock_value(
                devices.mythen.driver.detector_status, Mythen3DetectorState.IDLE
            )

    callback_on_mock_put(
        devices.panda._trigger,
        do_full_collection,
    )


def test_fast_trigger_with_run_engine(
    run_engine: RunEngine, fast_trigger_devices: FastTriggerDevices
):
    devices = fast_trigger_devices
    set_mock_value(devices.mythen.driver.detector_status, Mythen3DetectorState.RUNNING)

    number_of_frames = 1000

    _do_fast_collection_on_trigger(devices, number_of_frames)

    run_engine(
        fast_trigger_mythen(
            number_of_frames, 0.1, mercury_itc=devices.mercury_itc, **devices.common()
        )
    )
    get_mock_put(devices.mythen.driver.frames).assert_called_with(number_of_frames)
    get_mock_put(devices.panda._trigger).assert_has_calls(
        [call(False), call(True), call(False)]
    )


def test_psu_ramp_with_run_engine(
    run_engine: RunEngine, fast_trigger_devices: FastTriggerDevices
):
    devices = fast_trigger_devices
    set_mock_value(devices.mythen.driver.detector_status, Mythen3DetectorState.IDLE)
    number_of_frames = 4
    _do_fast_collection_on_trigger(devices, number_of_frames)

    run_engine(
        psu_ramp_with_fast_trigger(
            [1.0, 5.0], 0.2, 0.1, 0, mercury_itc=devices.mercury_itc, **devices.common()
        )
    )
    get_mock_put(devices.tenma_psu.current_sp).assert_has_calls([call(1.0), call(5.0)])
    get_mock_put(devices.mythen.driver.frames).assert_called_with(number_of_frames)
    get_mock_put(devices.panda._trigger).assert_has_calls(
        [call(False), call(True), call(False)]
    )
