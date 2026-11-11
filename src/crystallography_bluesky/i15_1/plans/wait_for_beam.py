import time

import bluesky.plan_stubs as bps
from bluesky.utils import MsgGenerator
from dodal.common import inject
from dodal.devices.beamlines.i15_1.beam_health import BeamHealth
from dodal.log import LOGGER

beam_health = inject("beam_health")


def wait_for_beam(beam_health: BeamHealth = beam_health) -> MsgGenerator[None]:
    t_start = time.time()
    while True:
        healthy: bool = yield from bps.rd(beam_health)
        if healthy:
            break
        LOGGER.warning(f"Beam has not been healthy for {time.time() - t_start} seconds")
        yield from bps.sleep(10)
