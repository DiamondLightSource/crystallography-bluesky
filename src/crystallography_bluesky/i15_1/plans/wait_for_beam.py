import time

import bluesky.plan_stubs as bps
from bluesky.utils import MsgGenerator
from dodal.devices.beamlines.i15_1.beam_health import BeamHealth
from dodal.log import LOGGER


def wait_for_beam(beam_health: BeamHealth) -> MsgGenerator:
    t_start = time.time()
    while True:
        healthy = yield from bps.rd(beam_health)
        if healthy:
            break
        LOGGER.warning(f"Beam has not been healthy for {time.time() - t_start} seconds")
        yield from bps.sleep(10)
