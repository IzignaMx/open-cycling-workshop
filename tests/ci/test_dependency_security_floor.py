"""Keep the reviewed two-package security correction narrow and fail closed."""

from __future__ import annotations

import copy
import hashlib
import json
import ssl
import tomllib
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import certifi
import pytest

ROOT = Path(__file__).parents[2]
CORRECTED = {"pillow": "13.0.0", "certifi": "2026.10.19"}
# All 41 other registry records from reviewed source tree 9cd12a9f, including
# versions, dependency edges, sources, artifact URLs, sizes and hashes. A later
# deliberate dependency change must independently review and update this seal.
UNRELATED_SHA256 = "8921ebb39e7d7091e8a38c1d150fd67a04860e44b5200555a95a0050e5470479"


def validate_dependencies(manifest: dict[str, Any], lock: dict[str, Any]) -> None:
    dependencies = manifest["project"]["dependencies"]
    assert [value for value in dependencies if value.lower().startswith("pillow")] == [
        "Pillow==13.0.0"
    ]
    # certifi stays HTTPX's development-transitive dependency, not production.
    assert not any(value.lower().startswith("certifi") for value in dependencies)
    packages = {package["name"]: package for package in lock["package"]}
    assert len(packages) == len(lock["package"])
    metadata = packages["open-cycling-workshop-platform"]["metadata"]["requires-dist"]
    assert [item for item in metadata if item["name"] == "pillow"] == [
        {"name": "pillow", "specifier": "==13.0.0"}
    ]
    for name, version in CORRECTED.items():
        package = packages[name]
        assert package["version"] == version
        assert package["source"] == {"registry": "https://pypi.org/simple"}
        artifacts = [package["sdist"], *package["wheels"]]
        assert artifacts
        for artifact in artifacts:
            url = urlparse(artifact["url"])
            assert url.scheme == "https" and url.netloc == "files.pythonhosted.org"
            assert artifact["hash"].startswith("sha256:")
            assert len(artifact["hash"]) == 71
    unrelated = [
        package
        for package in lock["package"]
        if "registry" in package["source"] and package["name"] not in CORRECTED
    ]
    assert len(unrelated) == 41
    sealed = json.dumps(unrelated, sort_keys=True, separators=(",", ":")).encode()
    assert hashlib.sha256(sealed).hexdigest() == UNRELATED_SHA256


def locked_inputs() -> tuple[dict[str, Any], dict[str, Any]]:
    return (
        tomllib.loads((ROOT / "services/platform/pyproject.toml").read_text()),
        tomllib.loads((ROOT / "uv.lock").read_text()),
    )


def test_corrected_dependency_pins_and_unrelated_lock_records() -> None:
    validate_dependencies(*locked_inputs())


@pytest.mark.parametrize("name,version", [("pillow", "12.3.0"), ("certifi", "2026.7.22")])
def test_previous_vulnerable_lock_version_is_refused(name: str, version: str) -> None:
    manifest, lock = locked_inputs()
    validate_dependencies(manifest, lock)
    package = next(package for package in lock["package"] if package["name"] == name)
    package["version"] = version
    with pytest.raises(AssertionError):
        validate_dependencies(manifest, lock)


@pytest.mark.parametrize("change", ["version", "artifact_hash", "added", "removed"])
def test_unrelated_lock_drift_is_refused(change: str) -> None:
    manifest, lock = locked_inputs()
    validate_dependencies(manifest, lock)
    package = next(package for package in lock["package"] if package["name"] == "httpx")
    if change == "version":
        package["version"] = "999.0.0"
    elif change == "artifact_hash":
        package["sdist"]["hash"] = "sha256:" + "0" * 64
    elif change == "added":
        extra = copy.deepcopy(package)
        extra["name"] = "unexpected-package"
        lock["package"].append(extra)
    else:
        lock["package"].remove(package)
    with pytest.raises(AssertionError):
        validate_dependencies(manifest, lock)


def test_corrected_ca_bundle_excludes_compromised_emsign_root() -> None:
    # GHSA-6q48-6c7w-9gw2: validate the installed bundle, not only a version label.
    context = ssl.create_default_context(cafile=certifi.where())
    certificates = context.get_ca_certs()
    assert certificates
    common_names = set()
    for certificate in certificates:
        subject = certificate["subject"]
        assert isinstance(subject, tuple)
        for rdn in subject:
            assert isinstance(rdn, tuple)
            for attribute in rdn:
                assert isinstance(attribute, tuple)
                name, value = attribute
                if name == "commonName":
                    common_names.add(value)
    assert "emSign ECC Root CA - G3" not in common_names
