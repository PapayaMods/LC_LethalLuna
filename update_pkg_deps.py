"""
"""

import requests
from dataclasses import dataclass
import argparse
from pathlib import Path
import json
from typing import Mapping, Sequence, Self
import concurrent.futures
from copy import deepcopy
import logging


logger = logging.getLogger(__name__)

_URL_API_EXP = "https://thunderstore.io/api/experimental"
_DEFAULT_MAX_WORKERS = 5  # Conservative value to avoid rate limiting


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
        url = f"{_URL_API_EXP}/package/{self.namespace}/{self.name}/"
        response = requests.get(url)
        response.raise_for_status()

        latest = response.json()["latest"]

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


def update_manifest_deps(
    manifest: Mapping, max_workers: int = _DEFAULT_MAX_WORKERS
) -> Mapping:
    manifest = deepcopy(manifest)
    deps_orig: Sequence[Package] = [
        Package.from_str(elem) for elem in manifest["dependencies"]
    ]

    deps_latest = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_pkg = {executor.submit(pkg.get_latest): pkg for pkg in deps_orig}
        for future in concurrent.futures.as_completed(future_to_pkg):
            pkg = future_to_pkg[future]
            try:
                deps_latest.append(future.result())
            except Exception as err:
                raise ValueError(
                    f"Failed to get latest version for package {pkg=}"
                ) from err

    manifest["dependencies"] = [str(pkg) for pkg in deps_latest]

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
