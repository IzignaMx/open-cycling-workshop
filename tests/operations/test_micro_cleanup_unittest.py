"""Mock-only micro cleanup regressions; never launch Docker, processes or trials."""

import json
import os
import tempfile
import textwrap
import unittest
from contextlib import ExitStack, chdir
from pathlib import Path
from unittest.mock import patch

from scripts.ci import quote_capacity_micro as module

ROOT = Path(__file__).resolve().parents[2]
CID = "c" * 64
IMAGE = "sha256:" + "b" * 64
TOKEN = "a" * 32
MICRO_KIND = "ocwp.quote_micro.cleanup_diagnostic"


class MicroCleanupTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.stack.enter_context(
            patch.object(
                module.subprocess, "Popen", side_effect=AssertionError("real process forbidden")
            )
        )
        self.owned = self.root / "quote-owned.json"
        self.receipt = self.root / "receipt.json"
        self.present = [CID]
        self.calls = []
        self.removed = []
        self.hint = ""
        self.fault = "create"
        self.identity_fault = None
        self.stack.enter_context(patch.object(module, "run", self.execute))

    def manifest(self):
        self.owned.with_suffix(".owner.json").write_text(
            json.dumps({"token": TOKEN, "images": dict.fromkeys(("db", "worker", "canary"), IMAGE)})
        )
        self.owned.with_suffix(".canary.cid").write_text(self.hint)

    def execute(self, args, **kwargs):
        self.calls.append((args, kwargs))
        if args[:3] == ["docker", "image", "inspect"]:
            return "e" * 40 if "ocwp.source-tree" in args[4] else IMAGE
        command = args[1]
        if command == "create":
            Path(args[args.index("--cidfile") + 1]).write_text(self.hint)
            if self.fault == "create":
                raise module.ProofFailure("command_timeout")
            return CID
        if command == "start":
            if self.fault == "start":
                raise module.ProofFailure("command_timeout")
            return CID
        if command == "exec":
            if self.fault == "probe":
                raise module.ProofFailure("command_timeout")
            return "probe"
        if command == "ps":
            if self.identity_fault == "list":
                raise module.ProofFailure("command_timeout")
            return "\n".join(self.present)
        if command == "inspect":
            if self.identity_fault == "inspect":
                raise module.ProofFailure("command_timeout")
            values = [IMAGE, TOKEN, f"/ocwp-quote-{TOKEN}-canary"]
            if self.identity_fault in ("image", "token", "name"):
                values[("image", "token", "name").index(self.identity_fault)] = "foreign"
            return "|".join(values)
        if command == "rm":
            self.assertEqual(args, ["docker", "rm", "--force", CID])
            if self.identity_fault == "remove":
                raise module.ProofFailure("command_timeout")
            if self.identity_fault != "still_present":
                self.present.remove(CID)
            self.removed.append(CID)
            return CID
        raise AssertionError(args)

    def supervisor(self):
        def inspect(*args):
            if self.fault == "inspect":
                raise module.ProofFailure("command_timeout")

        def privileges(*args):
            raise module.ProofFailure("command_timeout")

        with (
            patch.object(
                module,
                "source_query",
                lambda kind, execute: {"head": "d" * 40, "status": "", "tree": "e" * 40}[kind],
            ),
            patch.object(module, "uuid4", lambda: type("UUID", (), {"hex": TOKEN})()),
            patch.object(module.signal, "signal"),
            patch.object(module, "inspect_owned", inspect),
            patch.object(module, "parse_probe", lambda *args: {"cpu_usec": 0}),
            patch.object(module, "effective_privileges", privileges),
            self.assertRaisesRegex(module.ProofFailure, "micro_unqualified"),
        ):
            module.supervise("worker", "pg", "d" * 40, self.receipt, self.owned)
        return json.loads(self.receipt.read_text())

    def finalizer(self):
        workflow = (ROOT / ".github/workflows/quote-capacity-micro.yml").read_text()
        inline = textwrap.dedent(
            workflow.split("          python3 - <<'PY'\n", 1)[1].split("\n          PY", 1)[0]
        )
        with patch.dict(os.environ, {"RUNNER_TEMP": str(self.root)}), chdir(self.root):
            exec(compile(inline, "micro-workflow-finalizer", "exec"), {})

    def test_supervisor_empty_hint_reconciles_but_stays_uncertain(self):
        report = self.supervisor()
        self.assertEqual(self.removed, [CID])
        self.assertFalse(self.present)
        self.assertEqual((report["status"], report["cleanup"]), ("failed", "failed"))
        self.assertEqual(report["failure"], "command_timeout")

    def test_supervisor_partial_hint_reconciles_but_stays_uncertain(self):
        self.hint = "c" * 12
        self.test_supervisor_empty_hint_reconciles_but_stays_uncertain()

    def test_supervisor_complete_hint_retains_uncertainty(self):
        self.hint = CID
        self.test_supervisor_empty_hint_reconciles_but_stays_uncertain()

    def test_finalizer_empty_hint_removes_exact_owner(self):
        self.manifest()
        self.finalizer()
        self.assertEqual(self.removed, [CID])
        self.assertFalse(self.present)

    def test_finalizer_partial_hint_removes_exact_owner(self):
        self.hint = "c" * 12
        self.test_finalizer_empty_hint_removes_exact_owner()

    def test_finalizer_complete_hint_removes_exact_owner(self):
        self.hint = CID
        self.test_finalizer_empty_hint_removes_exact_owner()

    def test_failed_first_stem_does_not_skip_second_stem(self):
        self.hint = "invalid"
        self.manifest()
        self.owned = self.root / "quote-record-owned.json"
        self.hint = CID
        self.manifest()
        with self.assertRaisesRegex(SystemExit, "cleanup unverified"):
            self.finalizer()
        self.assertEqual(self.removed, [CID])

    def test_closed_operation_codes_preserve_initial_failure(self):
        for fault, expected in (
            ("create", "create"),
            ("inspect", "inspect"),
            ("start", "start"),
            ("probe", "resource_probe"),
            ("privileges", "privileges"),
        ):
            with self.subTest(fault=fault):
                self.fault = fault
                self.hint = CID
                self.present[:] = [CID]
                self.removed.clear()
                report = self.supervisor()
                self.assertEqual(report["failure_operation"], expected)
                self.assertEqual(report["command_stage"], "canary_containment")

    def test_metadata_failure_is_not_labeled_create_failure(self):
        original = Path.write_text
        self.fault = "privileges"
        self.hint = CID

        def write(path, *args, **kwargs):
            if path == self.owned:
                raise OSError("PRIVATE_CANARY")
            return original(path, *args, **kwargs)

        with patch.object(Path, "write_text", write):
            report = self.supervisor()
        self.assertEqual(report["failure_operation"], "record_identity")
        self.assertEqual(report["failure"], "invalid_evidence")
        self.assertNotIn("PRIVATE_CANARY", self.receipt.read_text())
        self.assertEqual(self.removed, [CID])

    def test_cleanup_failure_cannot_replace_initial_operation(self):
        self.identity_fault = "inspect"
        report = self.supervisor()
        self.assertEqual(report["failure_operation"], "create")
        observation = json.loads(self.receipt.with_suffix(".cleanup.json").read_text())
        self.assertEqual(observation["stage"], "inspect_identity")
        self.assertEqual(observation["outcome"], "failed")
        self.assertEqual(report["cleanup"], "failed")

    def test_micro_diagnostic_is_fixed_bounded_and_private(self):
        self.manifest()
        path = self.root / "diagnostic.json"
        module.diagnosed_full_reconcile(self.owned, self.execute, path, kind=MICRO_KIND)
        raw = path.read_text()
        report = json.loads(raw)
        self.assertEqual(report["kind"], MICRO_KIND)
        self.assertEqual(report["qualification"], "not_a_receipt")
        self.assertEqual(report["cidfiles"]["canary"], "empty")
        self.assertLess(len(raw), 1024)
        for forbidden in (CID, IMAGE, TOKEN, "PRIVATE_CANARY"):
            self.assertNotIn(forbidden, raw)

    def test_default_diagnostic_kind_unchanged(self):
        self.manifest()
        path = self.root / "diagnostic.json"
        module.diagnosed_full_reconcile(self.owned, self.execute, path)
        self.assertEqual(
            json.loads(path.read_text())["kind"], "ocwp.full_python.cleanup_diagnostic"
        )

    def test_diagnostic_sink_failure_does_not_prevent_cleanup(self):
        self.manifest()
        module.diagnosed_full_reconcile(
            self.owned, self.execute, self.root / "missing" / "diagnostic.json", kind=MICRO_KIND
        )
        self.assertEqual(self.removed, [CID])

    def test_invalid_kind_does_not_block_cleanup_or_echo_value(self):
        self.manifest()
        path = self.root / "diagnostic.json"
        module.diagnosed_full_reconcile(self.owned, self.execute, path, kind="PRIVATE_CANARY")
        self.assertEqual(self.removed, [CID])
        self.assertNotIn("PRIVATE_CANARY", path.read_text())
        self.assertEqual(
            json.loads(path.read_text())["kind"], "ocwp.full_python.cleanup_diagnostic"
        )

    def test_negative_owner_matrix_never_claims_absence(self):
        for fault in ("image", "token", "name", "list", "inspect", "remove", "still_present"):
            with self.subTest(fault=fault):
                self.identity_fault = fault
                self.present[:] = [CID]
                self.removed.clear()
                self.manifest()
                path = self.root / "diagnostic.json"
                with self.assertRaises(module.ProofFailure):
                    module.diagnosed_full_reconcile(self.owned, self.execute, path, kind=MICRO_KIND)
                self.assertEqual(json.loads(path.read_text())["outcome"], "failed")
                if fault != "still_present":
                    self.assertFalse(self.removed)
                self.assertEqual(self.present, [CID])

    def test_invalid_and_incomplete_without_manifest_never_remove(self):
        for hint, manifest in (("PRIVATE_CANARY", True), ("", False), ("c" * 12, False)):
            with self.subTest(hint=hint, manifest=manifest):
                self.hint = hint
                self.manifest()
                if not manifest:
                    self.owned.with_suffix(".owner.json").unlink()
                with self.assertRaises(module.ProofFailure):
                    module.full_reconcile(self.owned, self.execute)
                self.assertFalse(self.removed)

    def test_finalizer_rejects_wrong_identity_and_keeps_failure_diagnostic(self):
        self.manifest()
        self.identity_fault = "name"
        with self.assertRaisesRegex(SystemExit, "cleanup unverified"):
            self.finalizer()
        self.assertFalse(self.removed)
        report = json.loads(
            (self.root / "artifacts/quote-owned-finalizer-cleanup.json").read_text()
        )
        self.assertEqual(report["outcome"], "failed")
        self.assertEqual(report["failure"], "owner_identity_mismatch")

    def test_primary_diagnostic_distinguishes_absence_from_uncertain_workload(self):
        report = self.supervisor()
        observation = json.loads(self.receipt.with_suffix(".cleanup.json").read_text())
        self.assertEqual(observation["outcome"], "verified_absent")
        self.assertEqual(observation["qualification"], "not_a_receipt")
        self.assertEqual((report["status"], report["cleanup"]), ("failed", "failed"))

    def test_workflow_keeps_limits_and_fixed_diagnostic_paths(self):
        workflow = (ROOT / ".github/workflows/quote-capacity-micro.yml").read_text()
        self.assertIn("permissions:\n  contents: read", workflow)
        self.assertIn("timeout-minutes: 20", workflow)
        self.assertIn("timeout-minutes: 1", workflow)
        self.assertEqual(workflow.count("--kill-after=30s 120s python3"), 2)
        self.assertNotIn("workflow_dispatch", workflow)
        upload = workflow.split("- name: Upload bounded cleanup observations", 1)[1]
        for path in (
            "quote-capacity-micro.cleanup.json",
            "quote-record-feasibility.cleanup.json",
            "quote-owned-finalizer-cleanup.json",
            "quote-record-owned-finalizer-cleanup.json",
        ):
            self.assertIn("artifacts/" + path, upload)
        self.assertNotIn("*.json", upload)
        self.assertNotIn(".owner.json", upload)
        self.assertNotIn(".cid", upload)


if __name__ == "__main__":
    unittest.main()
