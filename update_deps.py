"""
"""

import sys
import requests
from dataclasses import dataclass
import argparse
from pathlib import Path
import json
from typing import Mapping, Sequence, Self

from copy import deepcopy
import logging


logger = logging.getLogger(__name__)

URL_API_EXP = "https://thunderstore.io/api/experimental"


@dataclass
class Package:
    """Represents a Thunderstore package."""

    namespace: str
    name: str
    version: str

    @staticmethod
    def from_str(full_name: str) -> Self:
        try:
            namespace, name, version = full_name.split("-")
        except ValueError as err:
            raise ValueError(f'Failed to parse package name "{full_name}"') from err

        return Package(namespace, name, version)

    def __str__(self) -> str:
        return f"{self.namespace}-{self.name}-{self.version}"

    def get_latest(self) -> Self:
        url = f"{URL_API_EXP}/package/{self.namespace}/{self.name}/"
        latest = requests.get(url).json()["latest"]

        pkg = Package(
            namespace=self.namespace, name=self.name, version=latest["version_number"]
        )
        logger.debug(f"self={repr(self)}, latest={repr(pkg)}")

        return pkg


def get_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ProgramName",
        description="What the program does",
        epilog="Text at the bottom of help",
    )
    parser.add_argument(
        "-i", "--input", help="Path to package manifest to update dependencies for."
    )
    parser.add_argument(
        "-o", "--output", help="Output path for updated package manifest."
    )
    parser.add_argument("-v", "--verbose", help="Verbose mode.", action="store_true")

    return parser


def update_manifest_deps(manifest: Mapping) -> Mapping:
    manifest = deepcopy(manifest)
    deps_orig: Sequence[Package] = [
        Package.from_str(elem) for elem in manifest["dependencies"]
    ]
    manifest["dependencies"] = [str(dep.get_latest()) for dep in deps_orig]

    return manifest


def main():
    args = get_arg_parser().parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)

    path_in = Path(args.input)
    path_out = Path(args.output)

    logger.debug(f"CLI args={args}")

    manifest_orig = json.loads(path_in.read_text())
    manifest_updated = update_manifest_deps(manifest_orig)

    path_out.write_text(json.dumps(manifest_updated, indent=4))


if __name__ == "__main__":
    main()
