"""Helpers for pip's experimental historical package store."""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from pip._vendor.packaging.markers import InvalidMarker, Marker
from pip._vendor.packaging.requirements import InvalidRequirement, Requirement
from pip._vendor.packaging.utils import canonicalize_name
from pip._vendor.packaging.version import InvalidVersion, Version

from pip._internal.metadata import BaseEnvironment, get_default_environment

if sys.version_info >= (3, 11):
    import tomllib as _tomllib
else:  # pragma: no cover - Python < 3.11
    from pip._vendor import tomli as _tomllib


@dataclass(frozen=True)
class StoredDistribution:
    name: str
    version: Version
    path: Path


def store_root() -> Path:
    return Path.home() / ".python" / "packages"


def iter_stored_distributions(name: str | None = None) -> list[StoredDistribution]:
    root = store_root()
    try:
        distributions = list(root.iterdir())
    except OSError:
        return []

    canonical_name = canonicalize_name(name) if name is not None else None
    result = []
    for distribution in distributions:
        if not distribution.is_dir():
            continue
        if (
            canonical_name is not None
            and canonicalize_name(distribution.name) != canonical_name
        ):
            continue
        try:
            versions = list(distribution.iterdir())
        except OSError:
            continue
        for version_path in versions:
            if not version_path.is_dir():
                continue
            try:
                version = Version(version_path.name)
            except InvalidVersion:
                continue
            result.append(StoredDistribution(distribution.name, version, version_path))
    return sorted(
        result,
        key=lambda item: (canonicalize_name(item.name), item.version),
    )


def find_stored(requirement: Requirement) -> StoredDistribution | None:
    candidates = [
        distribution
        for distribution in iter_stored_distributions(requirement.name)
        if requirement.specifier.contains(distribution.version, prereleases=True)
    ]
    return max(candidates, key=lambda item: item.version, default=None)


def find_ordinary(
    requirement: Requirement,
    environment: BaseEnvironment | None = None,
) -> tuple[str, str] | None:
    if environment is None:
        environment = get_default_environment()
    distribution = environment.get_distribution(requirement.name)
    if distribution is None:
        return None
    try:
        version = Version(str(distribution.version))
    except InvalidVersion:
        return None
    if not requirement.specifier.contains(version, prereleases=True):
        return None
    return distribution.raw_name, str(distribution.version)


def _read_toml(path: Path) -> dict[str, object] | None:
    try:
        with path.open("rb") as file:
            return _tomllib.load(file)
    except (OSError, _tomllib.TOMLDecodeError):
        return None


def _discover_project(start: str | os.PathLike[str] | None = None) -> Path | None:
    explicit = os.environ.get("PYTHONHISTORICALPROJECT")
    if explicit:
        project = Path(explicit).expanduser().absolute()
        if project.name in {"pylock.toml", "pyproject.toml"}:
            project = project.parent
        if (project / "pylock.toml").is_file() or (
            project / "pyproject.toml"
        ).is_file():
            return project
        return None

    directory = Path(start or os.getcwd()).absolute()
    if directory.is_file():
        directory = directory.parent
    while True:
        if (directory / "pylock.toml").is_file() or (
            directory / "pyproject.toml"
        ).is_file():
            return directory
        if directory.parent == directory:
            return None
        directory = directory.parent


def _applicable(requirement: Requirement) -> bool:
    return requirement.marker is None or requirement.marker.evaluate()


def _project_requirements(path: Path) -> dict[str, Requirement]:
    data = _read_toml(path)
    if data is None:
        return {}
    project = data.get("project")
    if not isinstance(project, dict):
        return {}
    dependencies = project.get("dependencies", ())
    if not isinstance(dependencies, list):
        return {}

    result: dict[str, Requirement] = {}
    for text in dependencies:
        if not isinstance(text, str):
            continue
        try:
            requirement = Requirement(text)
        except InvalidRequirement:
            continue
        if requirement.url is None and _applicable(requirement):
            result[canonicalize_name(requirement.name)] = requirement
    return result


def _lock_is_compatible(data: Mapping[str, object]) -> bool:
    if data.get("lock-version") != "1.0":
        return False
    requires_python = data.get("requires-python")
    if isinstance(requires_python, str):
        import platform

        try:
            requirement = Requirement(f"python{requires_python}")
        except InvalidRequirement:
            return False
        if not requirement.specifier.contains(platform.python_version()):
            return False
    environments = data.get("environments")
    if isinstance(environments, list) and environments:
        try:
            if not any(Marker(marker).evaluate() for marker in environments):
                return False
        except (InvalidMarker, TypeError, ValueError):
            return False
    return True


def _lock_requirements(path: Path) -> dict[str, Requirement] | None:
    data = _read_toml(path)
    if data is None or not _lock_is_compatible(data):
        return None
    packages = data.get("packages", ())
    if not isinstance(packages, list):
        return None

    result: dict[str, Requirement] = {}
    for package in packages:
        if not isinstance(package, dict):
            return None
        marker = package.get("marker")
        if isinstance(marker, str):
            try:
                if not Marker(marker).evaluate():
                    continue
            except InvalidMarker:
                return None
        name = package.get("name")
        version = package.get("version")
        if not isinstance(name, str) or not isinstance(version, str):
            continue
        try:
            requirement = Requirement(f"{name}=={version}")
        except InvalidRequirement:
            return None
        canonical_name = canonicalize_name(name)
        previous = result.get(canonical_name)
        if previous is not None and previous.specifier != requirement.specifier:
            return None
        result[canonical_name] = requirement
    return result


def project_requirements(
    start: str | os.PathLike[str] | None = None,
) -> dict[str, Requirement] | None:
    project = _discover_project(start)
    if project is None:
        return None
    lock_path = project / "pylock.toml"
    if lock_path.is_file():
        locked = _lock_requirements(lock_path)
        if locked is not None:
            return locked
    project_path = project / "pyproject.toml"
    if project_path.is_file():
        return _project_requirements(project_path)
    return {}


def store_destination(name: str, version: str) -> Path:
    parsed_version = Version(version)
    if any(separator in name for separator in (os.sep, os.altsep) if separator):
        raise ValueError(f"invalid distribution name: {name!r}")
    return store_root() / name / str(parsed_version)
