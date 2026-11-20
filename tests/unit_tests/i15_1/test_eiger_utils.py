from bluesky.simulators import RunEngineSimulator, assert_message_and_return_remaining

from crystallography_bluesky.i15_1.plans.eiger_utils import eiger_hv_reset


def test_eiger_hv_reset_runs_reset_and_waits(eiger):
    time_for_reset_seconds = 10
    minutes_to_wait_after_reset = 2
    msgs = RunEngineSimulator().simulate_plan(
        eiger_hv_reset(
            time_for_reset_seconds,
            minutes_to_wait_after_reset,
            eiger,
        )
    )

    msgs = assert_message_and_return_remaining(
        msgs,
        predicate=lambda msg: (
            msg.command == "set"
            and msg.obj == eiger.detector.hv_reset_duration
            and msg.args[0] == time_for_reset_seconds
        ),
    )
    msgs = assert_message_and_return_remaining(
        msgs,
        predicate=lambda msg: (
            msg.command == "trigger" and msg.obj == eiger.detector.hv_reset
        ),
    )
    assert_message_and_return_remaining(
        msgs,
        predicate=lambda msg: (
            msg.command == "sleep"
            and msg.args[0] == time_for_reset_seconds + 60 * minutes_to_wait_after_reset
        ),
    )
