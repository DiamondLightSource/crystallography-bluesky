import bluesky.plan_stubs as bps
from bluesky.utils import MsgGenerator
from dodal.devices.zebra.zebra import TrigSource, Zebra


def update_number_of_frames_for_hardware_triggering(
    zebra: Zebra, frames: int, time_between_frames: float, group: str | None = None
) -> MsgGenerator:
    _group = group if group is not None else "zebra_update_frames"
    yield from bps.abs_set(zebra.pc.pulse_max, frames, group=_group)
    yield from bps.abs_set(
        zebra.pc.gate_width, frames * time_between_frames, group=_group
    )
    if group is None:
        yield from bps.wait(_group)


def setup_zebra_for_hardware_triggering(
    zebra: Zebra,
    frames: int,
    time_between_frames: float,
    pulse_width: float | None = None,
) -> MsgGenerator:
    # Note that this all assumes the time units (PC_TSPRE PV) are set to s, rather than
    # ms or 10s

    group = "zebra_setup"

    pulse_width = pulse_width if pulse_width is not None else time_between_frames / 2

    assert pulse_width < time_between_frames, (
        f"Cannot have a pulse width ({pulse_width}) "
        + f"greater than or equal to the time between frames ({time_between_frames})"
    )

    yield from bps.abs_set(zebra.pc.pulse_source, TrigSource.TIME, group=group)
    yield from bps.abs_set(zebra.pc.pulse_start, 0.0, group=group)
    yield from bps.abs_set(zebra.pc.pulse_width, pulse_width, group=group)
    yield from bps.abs_set(zebra.pc.pulse_step, time_between_frames, group=group)

    yield from bps.abs_set(zebra.pc.gate_source, TrigSource.TIME, group=group)
    yield from bps.abs_set(zebra.pc.gate_start, 0.0, group=group)
    yield from bps.abs_set(zebra.pc.num_gates, 1, group=group)

    update_number_of_frames_for_hardware_triggering(
        zebra, frames, time_between_frames, group
    )

    # Set eiger and i0 to be triggered directly from PC_PULSE
    yield from bps.abs_set(
        zebra.output.out_pvs[zebra.mapping.outputs.TTL_EIGER],
        zebra.mapping.sources.PC_PULSE,
        group=group,
    )
    yield from bps.abs_set(
        zebra.output.out_pvs[zebra.mapping.outputs.TTL_I0],
        zebra.mapping.sources.PC_PULSE,
        group=group,
    )
    yield from bps.wait(group)


def setup_zebra_for_software_triggering(zebra: Zebra) -> MsgGenerator:
    group = "zebra_setup"

    # Set eiger and i0 to be triggered directly from SOFT_IN1
    yield from bps.abs_set(
        zebra.output.out_pvs[zebra.mapping.outputs.TTL_EIGER],
        zebra.mapping.sources.SOFT_IN1,
        group=group,
    )
    yield from bps.abs_set(
        zebra.output.out_pvs[zebra.mapping.outputs.TTL_I0],
        zebra.mapping.sources.SOFT_IN1,
        group=group,
    )
    yield from bps.wait(group)
