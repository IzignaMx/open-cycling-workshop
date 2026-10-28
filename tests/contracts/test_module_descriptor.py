from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/plugins/validate_manifest.py"
TARGET = "ocwp-source:a960bddb94189c6c74c7f3d0a72472636c3caced"


@lru_cache
def module():
    assert SCRIPT.is_file(), "M0 descriptor validator is not implemented"
    spec = importlib.util.spec_from_file_location("descriptor_m0", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def valid():
    return {
        "schema": 1,
        "profile": "ocwp.module-descriptor.m0",
        "id": "org.example.readonly-info",
        "name": "Información de ejemplo",
        "version": "0.0.0-m0",
        "license": "AGPL-3.0-only",
        "core": {"requires": TARGET},
        "runtime": {"type": "official-build"},
        "permissions": [],
        "network": {"hosts": []},
        "events": {"subscribes": []},
        "secrets": [],
        "data": {"owns": []},
        "ui": {"slots": []},
        "offline": {"mode": "online-only"},
    }


def raw(data):
    return json.dumps(data, ensure_ascii=True).encode()


def reject(data, expected=None):
    mod = module()
    with pytest.raises(mod.DescriptorError) as caught:
        mod.validate_descriptor(data)
    assert caught.value.code in mod.ERROR_CODES
    assert str(caught.value) == caught.value.code
    assert len(str(caught.value)) <= 24
    if expected:
        assert caught.value.code == expected


def test_valid_descriptor_preserved_and_external_class_does_not_grant_authority():
    data = valid()
    before = copy.deepcopy(data)
    assert module().validate_descriptor(raw(data)) == data == before
    data["runtime"]["type"] = "external-connector"
    result = module().validate_descriptor(raw(data))
    assert result["permissions"] == []
    assert result["network"] == {"hosts": []}
    assert result["runtime"]["type"] == "external-connector"


@pytest.mark.parametrize("filename", ["official-descriptor.m0.json", "external-descriptor.m0.json"])
def test_committed_examples_validate(filename):
    mod = module()
    source = ROOT / "packages/plugin-sdk/examples" / filename
    assert mod.validate_descriptor(source.read_bytes())["core"]["requires"] == TARGET


@pytest.mark.parametrize(
    "data,code",
    [
        (b"x" * 16385, "E_SIZE"),
        (b"\xff", "E_UTF8"),
        (b"\xef\xbb\xbf{}", "E_UTF8"),
        (b"{} {}", "E_JSON"),
        (b"{", "E_JSON"),
        (b"null", "E_SCHEMA"),
        (b"[]", "E_SCHEMA"),
        (b'{"schema":1,"schema":1}', "E_DUPLICATE_KEY"),
        (b'{"a":{"b":1,"b":1}}', "E_DUPLICATE_KEY"),
        (b'{"schema":1.0}', "E_NUMBER"),
        (b'{"schema":1e0}', "E_NUMBER"),
        (b'{"schema":NaN}', "E_NUMBER"),
        (b'{"schema":Infinity}', "E_NUMBER"),
        (b'{"schema":12345678901}', "E_NUMBER"),
        (b"[" * 1500 + b"]" * 1500, "E_DEPTH"),
        (b'{"name":"\\ud800"}', "E_STRING"),
        (b'{"name":"\\n"}', "E_STRING"),
        (b'{"\\udfff":1}', "E_STRING"),
        (b'{"name":"\\u202e"}', "E_STRING"),
    ],
)
def test_parser_envelope_fixed_errors(data, code):
    reject(data, code)


@pytest.mark.parametrize("data", [None, "text", bytearray(b"{}"), 1, True])
def test_only_immutable_bytes_input(data):
    reject(data, "E_INPUT_TYPE")


@pytest.mark.parametrize(
    "key,value",
    [
        ("schema", True),
        ("schema", 2),
        ("profile", "ocwp.module-descriptor.v1"),
        ("version", "1.0.0"),
        ("license", "MIT"),
        ("id", "../module"),
        ("id", "org.Example.module"),
        ("id", "org.only"),
        ("id", "a" * 129),
        ("name", ""),
        ("name", "x" * 81),
        ("permissions", ["inventory.read"]),
        ("secrets", ["owner-password"]),
    ],
)
def test_closed_profile_and_no_authority(key, value):
    data = valid()
    data[key] = value
    reject(raw(data), "E_SCHEMA")


@pytest.mark.parametrize(
    "key,value",
    [
        ("core", {"requires": ">=1.0.0 <2.0.0"}),
        ("core", {"requires": "0.1.0.dev0"}),
        ("core", {"requires": "0.1.0-dev.0"}),
        ("core", {"requires": "ocwp-source:a960bdd"}),
        ("core", {"requires": TARGET[:-1] + "0"}),
        ("runtime", {"type": "dynamic-python"}),
        ("network", {"hosts": ["example.com"]}),
        ("events", {"subscribes": ["service_order.ready"]}),
        ("data", {"owns": ["customers"]}),
        ("ui", {"slots": ["sidebar"]}),
        ("offline", {"mode": "queue"}),
    ],
)
def test_unsupported_targets_and_integration_requests(key, value):
    data = valid()
    data[key] = value
    reject(raw(data), "E_SCHEMA")


@pytest.mark.parametrize(
    "key",
    [
        "platform",
        "capabilities",
        "subscriptions",
        "hooks",
        "entrypoint",
        "importPath",
        "command",
        "source",
        "official",
        "trust",
    ],
)
def test_legacy_or_executable_or_trust_fields_rejected(key):
    data = valid()
    data[key] = "sensitive-canary-do-not-echo"
    reject(raw(data), "E_SCHEMA")


@pytest.mark.parametrize("key", ["core", "runtime", "network", "events", "data", "ui", "offline"])
def test_nested_unknown_keys_fail_closed(key):
    data = valid()
    data[key]["unknown"] = "sensitive-canary"
    reject(raw(data), "E_SCHEMA")


def test_every_required_field_is_enforced():
    for key in valid():
        data = valid()
        del data[key]
        reject(raw(data), "E_SCHEMA")


def test_raw_size_boundary_and_depth():
    encoded = raw(valid())
    assert module().validate_descriptor(encoded + b" " * (16384 - len(encoded)))
    reject(encoded + b" " * (16385 - len(encoded)), "E_SIZE")
    reject(b"[" * 9 + b"0" + b"]" * 9, "E_DEPTH")


def test_unknown_trusted_schema_keyword_fails_closed():
    mod = module()
    with pytest.raises(mod.DescriptorError, match="E_SCHEMA_DEFINITION"):
        mod.check_schema_definition({"type": "object", "remoteRef": "https://example.com"})
    with pytest.raises(mod.DescriptorError, match="E_SCHEMA_DEFINITION"):
        mod.check_schema_definition({"type": "object", "properties": {"x": {"unsupported": True}}})


def test_cli_summary_never_echoes_payload(tmp_path):
    module()
    path = tmp_path / "descriptor.json"
    path.write_bytes(raw(valid()))
    command = [sys.executable, str(SCRIPT), str(path)]
    passed = subprocess.run(command, capture_output=True, text=True, check=False)
    assert passed.returncode == 0
    assert passed.stdout.strip() == "descriptor valid; runtime not evaluated"
    path.write_bytes(b'{"password":"sensitive-canary-do-not-echo"}')
    failed = subprocess.run(command, capture_output=True, text=True, check=False)
    assert failed.returncode == 1
    assert failed.stderr.strip() == "E_SCHEMA"
    assert "sensitive-canary" not in failed.stdout + failed.stderr
    assert path.read_bytes() == b'{"password":"sensitive-canary-do-not-echo"}'
    assert sorted(p.name for p in tmp_path.iterdir()) == ["descriptor.json"]


def test_cli_bounds_the_read_before_parsing(tmp_path, monkeypatch, capsys):
    mod = module()
    path = tmp_path / "huge.json"
    path.write_bytes(b"x" * 20000)
    requested = []
    original = Path.open

    class Reader:
        def __init__(self, file):
            self.file = file

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.file.close()

        def read(self, size):
            requested.append(size)
            return self.file.read(size)

    monkeypatch.setattr(
        Path, "open", lambda self, *args, **kwargs: Reader(original(self, *args, **kwargs))
    )
    assert mod.main([str(path)]) == 1
    assert requested == [16385]
    assert capsys.readouterr().err.strip() == "E_SIZE"


def test_sdk_runtime_exports_are_unchanged():
    assert (ROOT / "packages/plugin-sdk/src/index.ts").read_text().endswith("export {}\n")


@pytest.mark.parametrize(
    "schema",
    [
        {"type": "string", "maxItems": 0},
        {"type": "integer", "pattern": ".*"},
        {"type": "array", "maxItems": False, "items": False},
    ],
)
def test_trusted_schema_rejects_inapplicable_or_boolean_constraints(schema):
    with pytest.raises(module().DescriptorError, match="E_SCHEMA_DEFINITION"):
        module().check_schema_definition(schema)


def test_cli_schema_failure_is_bounded(tmp_path, monkeypatch, capsys):
    mod = module()
    descriptor = tmp_path / "descriptor.json"
    descriptor.write_bytes(raw(valid()))
    missing = tmp_path / "missing-schema.json"
    monkeypatch.setattr(mod, "SCHEMA_PATH", missing)
    assert mod.main([str(descriptor)]) == 1
    assert capsys.readouterr().err.strip() == "E_SCHEMA_DEFINITION"


@pytest.mark.parametrize(
    "schema", [True, False, {"type": "integer", "enum": [True]}, {"type": "integer", "const": True}]
)
def test_trusted_schema_cannot_admit_boolean_root_or_mixed_constant_types(schema):
    with pytest.raises(module().DescriptorError, match="E_SCHEMA_DEFINITION"):
        module().check_schema_definition(schema)


def test_trusted_pattern_subset_must_be_anchored():
    with pytest.raises(module().DescriptorError, match="E_SCHEMA_DEFINITION"):
        module().check_schema_definition({"type": "string", "pattern": "module"})
