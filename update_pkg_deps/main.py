import argparse
import concurrent.futures
import json
import logging
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Self, Sequence

import requests

logger = logging.getLogger(__name__)

_URL_API_EXP = "https://thunderstore.io/api/experimental"
_DEFAULT_MAX_WORKERS = 5  # Conservative value to avoid rate limiting
_TIMEOUT = 10  # Seconds
_ENCODING = "utf-8"


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

    def get_latest(self, timeout: float = _TIMEOUT) -> Self:
        url = f"{_URL_API_EXP}/package/{self.namespace}/{self.name}/"
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()

        latest = response.json()["latest"]

        pkg = Package(
            namespace=self.namespace, name=self.name, version=latest["version_number"]
        )
        logger.debug("self=%s, latest=%s", repr(self), repr(pkg))

        return pkg


def update_manifest_deps(
    manifest: Mapping, max_workers: int = _DEFAULT_MAX_WORKERS
) -> Mapping:
    """Updates the provided package's manifest dependencies to the latest versions."""
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

    manifest["dependencies"] = sorted([str(pkg) for pkg in deps_latest])

    return manifest


def get_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="update_pkg_deps",
        description="Updates dependencies to the latest version for the provided package manifest.",
    )
    parser.add_argument(
        "-i",
        "--input",
        help="Path to package manifest to update dependencies for.",
        required=True,
        type=str,
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Output path for updated package manifest.",
        required=True,
        type=str,
    )
    parser.add_argument(
        "--max-workers",
        help="Maximum number of API workers",
        type=int,
        default=_DEFAULT_MAX_WORKERS,
    )
    parser.add_argument("-v", "--verbose", help="Verbose mode.", action="store_true")

    return parser


def main():
    args = get_arg_parser().parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)
    logger.info("Log level set to %s", log_level)

    path_out = Path(args.output)
    path_in = Path(args.input)

    logger.info("Loading package manifest: %s", path_in)
    manifest_orig = json.loads(path_in.read_text(encoding=_ENCODING))

    logger.info("Updating package manifest...")
    manifest_updated = update_manifest_deps(manifest_orig, max_workers=args.max_workers)

    logger.info("Writing package manifest: %s", path_out)
    path_out.write_text(json.dumps(manifest_updated, indent=4), encoding=_ENCODING)


if __name__ == "__main__":
    main()
