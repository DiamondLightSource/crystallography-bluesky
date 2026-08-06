import bluesky.plan_stubs as bps
from bluesky.utils import MsgGenerator
from dodal.devices.zebra.zebra import TrigSource, Zebra


def setup_zebra_for_external_edge_triggering(
    zebra: Zebra, frames: int, time_between_frames: float
) -> MsgGenerator:
    yield from bps.mv(zebra.pc.pulse_max, frames)
    yield from bps.mv(zebra.pc.pulse_source, TrigSource.TIME)
    yield from bps.mv(zebra.pc.pulse_start, 0.0)
    yield from bps.mv(zebra.pc.pulse_width, time_between_frames / 2)
    yield from bps.mv(zebra.pc.pulse_step, time_between_frames)
    yield from bps.mv(zebra.pc.gate_width, frames * time_between_frames)

    # Set eiger and i0 to be triggered directly from PC_PULSE
    yield from bps.mv(
        zebra.output.out_pvs[zebra.mapping.outputs.TTL_EIGER],
        zebra.mapping.sources.PC_PULSE,
    )
    yield from bps.mv(
        zebra.output.out_pvs[zebra.mapping.outputs.TTL_I0],
        zebra.mapping.sources.PC_PULSE,
    )


def setup_zebra_for_software_triggering(zebra: Zebra) -> MsgGenerator:
    # Set eiger and i0 to be triggered directly from SOFT_IN1
    yield from bps.mv(
        zebra.output.out_pvs[zebra.mapping.outputs.TTL_EIGER],
        zebra.mapping.sources.SOFT_IN1,
    )
    yield from bps.mv(
        zebra.output.out_pvs[zebra.mapping.outputs.TTL_I0],
        zebra.mapping.sources.SOFT_IN1,
    )
