import os, sys

sys.path.append("/dls_sw/i11/software/blueapi/scratch/crystallography-bluesky/src")

import crystallography_bluesky.i11
from crystallography_bluesky.common.utils.beamline_client import BlueAPIPythonClient
# from crystallography_bluesky.i11.plans import mythen_scan

BL = os.environ["BEAMLINE"]

blueapi_config_path = (
    f"{os.path.dirname(crystallography_bluesky.i11.__file__)}/{BL}_blueapi_config.yaml"
)

client = BlueAPIPythonClient(BL, blueapi_config_path, "cm40625-4")


parameters = {"start": 90, "stop": 92, "step": 0.5, "duration": 1.0}
client.run("mythen_scan", parameters)
