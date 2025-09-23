"""Interface for ``python -m crystallography_bluesky``."""

import os

# from argparse import ArgumentParser
# from collections.abc import Sequence
import click

import crystallography_bluesky.i11

from . import __version__

__all__ = ["main"]

BL = os.environ.get("BEAMLINE")


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, message="%(version)s")
@click.pass_context
def main(ctx: click.Context) -> None:
    if ctx.invoked_subcommand is None:
        print("Please invoke subcommand!")


blueapi_config_path = (
    f"{os.path.dirname(crystallography_bluesky.i11.__file__)}/{BL}_blueapi_config.yaml"
)


@main.command(name="login")
def login():
    os.system(
        f"blueapi -c {blueapi_config_path} login"  # noqa
    )


if __name__ == "__main__":
    main()
