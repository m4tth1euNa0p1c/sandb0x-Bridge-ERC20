"""Tests hors réseau du jalon 1 : garde-fous, preuves et orchestration limitée."""
from __future__ import annotations

from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("bridge_tooling", REPO / "scripts/bridge.py")
bridge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bridge)


def read_profile(name="local-fast"):
    return json.loads((REPO / f"sandbox/profiles/{name}.json").read_text(encoding="utf-8"))


class ProfilePolicyTests(unittest.TestCase):
    def test_known_local_profiles_are_accepted(self):
        for name in ("local-fast", "local-besu"):
            with self.subTest(name=name):
                bridge.validate_profile(read_profile(name))

    def test_unknown_profile_is_rejected_before_reading_configuration(self):
        with patch.object(bridge, "read_json") as read:
            for name in ("mainnet", "../local-fast", "local-fast; echo injected"):
                with self.subTest(name=name), self.assertRaises(bridge.BridgeError):
                    bridge.profile(name, runnable=True)
            read.assert_not_called()

    def test_non_test_profile_is_rejected(self):
        p = read_profile()
        p["test_only"] = False
        with self.assertRaises(bridge.BridgeError):
            bridge.validate_profile(p)

    def test_mainnet_and_unapproved_chain_pairs_are_rejected(self):
        for ids in ([1, 31338], [31337, 31337], [31338, 31337], [31339, 31340]):
            with self.subTest(ids=ids):
                p = read_profile()
                for chain, chain_id in zip(p["chains"], ids):
                    chain["chain_id"] = chain_id
                with self.assertRaises(bridge.BridgeError):
                    bridge.validate_profile(p)

    def test_external_and_ambiguous_rpc_endpoints_are_rejected(self):
        for endpoint in ("https://example.invalid/rpc", "http://127.0.0.1.example.invalid:18545",
                         "http://127.0.0.1:18545@external.invalid", "http://localhost:18545"):
            with self.subTest(endpoint=endpoint):
                p = read_profile()
                p["chains"][0]["rpc_host"] = endpoint
                with self.assertRaises(bridge.BridgeError):
                    bridge.validate_profile(p)

    def test_unsupported_decimals_and_evm_target_are_rejected(self):
        for field, value in (("token_decimals", 6), ("token_decimals", "18"), ("evm_target", "cancun")):
            with self.subTest(field=field, value=value):
                p = read_profile()
                p[field] = value
                with self.assertRaises(bridge.BridgeError):
                    bridge.validate_profile(p)

    def test_missing_or_unknown_finality_is_rejected(self):
        for policy in (None, {}, {"mode": "latest"}, {"mode": "automatic-fallback"}):
            with self.subTest(policy=policy):
                p = read_profile()
                p["chains"][0]["finality"] = policy
                with self.assertRaises(bridge.BridgeError):
                    bridge.validate_profile(p)

    def test_confirmation_depth_requires_a_bounded_positive_integer(self):
        for depth in (None, 0, -1, 129, 1.5, "3", True):
            with self.subTest(depth=depth):
                p = read_profile()
                p["chains"][0]["finality"] = {"mode": "confirmations", "depth": depth}
                with self.assertRaises(bridge.BridgeError):
                    bridge.validate_profile(p)

    def test_qbft_policy_cannot_be_applied_to_anvil(self):
        p = read_profile()
        p["chains"][0]["finality"] = {"mode": "qbft-local"}
        with self.assertRaises(bridge.BridgeError):
            bridge.validate_profile(p)

    def test_confirmation_policy_cannot_replace_besu_qbft_silently(self):
        p = read_profile("local-besu")
        p["chains"][0]["finality"] = {"mode": "confirmations", "depth": 3}
        with self.assertRaises(bridge.BridgeError):
            bridge.validate_profile(p)


class IntegrationGateTests(unittest.TestCase):
    def test_disabled_profile_can_be_inspected_without_activation(self):
        p = bridge.profile("integration-testnet")
        self.assertFalse(p["enabled"])
        self.assertIsNone(p["chains"][1]["chain_id"])
        self.assertIsNone(p["chains"][1]["rpc_http"])

    def test_integration_execution_paths_reject_before_any_external_action(self):
        calls = (
            lambda: bridge.up("integration-testnet"),
            lambda: bridge.bootstrap("integration-testnet"),
            lambda: bridge.prove("integration-testnet"),
            lambda: bridge.compose("integration-testnet", ["up"]),
        )
        with patch.object(bridge, "run") as run, patch.object(bridge, "rpc") as rpc:
            for operation in calls:
                with self.subTest(operation=operation), self.assertRaises(bridge.BridgeError):
                    operation()
            run.assert_not_called()
            rpc.assert_not_called()

    def test_editing_enabled_cannot_activate_integration(self):
        p = read_profile("integration-testnet")
        p["enabled"] = True
        with patch.object(bridge, "read_json", return_value=p), patch.object(bridge, "run") as run, patch.object(bridge, "rpc") as rpc:
            with self.assertRaises(bridge.BridgeError):
                bridge.up("integration-testnet")
            run.assert_not_called()
            rpc.assert_not_called()


class StartupSafetyTests(unittest.TestCase):
    def test_failed_compose_validation_prevents_startup(self):
        for name in ("local-fast", "local-besu"):
            with self.subTest(profile=name), tempfile.TemporaryDirectory(prefix="t3l4n-test-startup-") as d:
                runtime = Path(d)
                (runtime / "postgres_password").write_text("public test witness", encoding="utf-8")
                with patch.object(bridge, "runtime", return_value=runtime), patch.object(bridge, "validate_compose", side_effect=bridge.BridgeError("configuration refusée")) as validate, patch.object(bridge, "compose") as compose, patch.object(bridge, "docs_build"), patch.object(bridge, "chain_observation", return_value={}), redirect_stdout(io.StringIO()):
                    with self.assertRaises(bridge.BridgeError):
                        bridge.up(name)
                    validate.assert_called_once_with(name)
                    compose.assert_not_called()


class ComposeMountPolicyTests(unittest.TestCase):
    def config(self):
        return {
            "services": {"docs": {
                "user": "10001:10001", "read_only": True, "cap_drop": ["ALL"],
                "security_opt": ["no-new-privileges:true"], "mem_limit": 67108864,
                "cpus": 1, "pids_limit": 32, "logging": {"driver": "json-file", "options": {"max-size": "5m", "max-file": "2"}},
                "image": bridge.lock()["images"]["probe"],
                "volumes": [{"type": "bind", "source": str(bridge.ROOT / "site"), "target": "/site", "read_only": True}],
                "networks": {"documentation": None},
            }},
            "networks": {"documentation": {"internal": True}},
        }

    def validate(self, config):
        with patch.object(bridge, "compose", return_value={"stdout": json.dumps(config)}):
            return bridge.validate_compose("local-fast")

    def test_read_only_site_mount_is_authorized_for_docs(self):
        self.validate(self.config())

    def test_documented_no_new_privileges_forms_are_accepted(self):
        for option in ("no-new-privileges", "no-new-privileges:true", "no-new-privileges=true"):
            with self.subTest(option=option):
                config = self.config()
                config["services"]["docs"]["security_opt"] = [option]
                self.validate(config)

    def test_disabled_or_ambiguous_no_new_privileges_is_rejected(self):
        for options in ([], ["no-new-privileges:false"], ["no-new-privileges=false"],
                        ["no-new-privileges:0"], ["label:no-new-privileges:true"],
                        ["no-new-privileges:true", "no-new-privileges:false"],
                        ["no-new-privileges=false", "no-new-privileges=true"]):
            with self.subTest(options=options):
                config = self.config()
                config["services"]["docs"]["security_opt"] = options
                with self.assertRaises(bridge.BridgeError):
                    self.validate(config)

    def test_home_subdirectory_and_other_unapproved_binds_are_rejected(self):
        for source in (Path.home() / ".ssh", bridge.ROOT / "scripts", bridge.ROOT.parent):
            with self.subTest(source=source):
                config = self.config()
                config["services"]["docs"]["volumes"][0]["source"] = str(source)
                with self.assertRaises(bridge.BridgeError):
                    self.validate(config)

    def test_authorized_bind_cannot_be_mounted_writable_or_at_another_target(self):
        for change in ({"read_only": False}, {"target": "/unexpected"}):
            with self.subTest(change=change):
                config = self.config()
                config["services"]["docs"]["volumes"][0].update(change)
                with self.assertRaises(bridge.BridgeError):
                    self.validate(config)

    def test_site_bind_cannot_be_granted_to_an_unrelated_service(self):
        config = self.config()
        config["services"]["postgres"] = config["services"].pop("docs")
        with self.assertRaises(bridge.BridgeError):
            self.validate(config)


class SourceFingerprintTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="t3l4n-test-snapshot-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root_patch = patch.object(bridge, "ROOT", self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)

    def snapshot(self, files):
        with patch.object(bridge, "run", return_value={"stdout": "\0".join(files) + "\0"}):
            return bridge.source_snapshot()

    def test_file_hash_is_the_hash_of_exact_bytes(self):
        path = self.root / "example.py"
        raw = b"print('test')\r\n"
        path.write_bytes(raw)
        snap = self.snapshot(["example.py"])
        self.assertEqual(snap["files"], {"example.py": hashlib.sha256(raw).hexdigest()})

    def test_content_changes_and_file_deletion_change_source_fingerprint(self):
        path = self.root / "example.py"
        path.write_bytes(b"version one\n")
        first = self.snapshot(["example.py"])
        path.write_bytes(b"version two\n")
        second = self.snapshot(["example.py"])
        path.unlink()
        third = self.snapshot(["example.py"])
        self.assertNotEqual(first["sha256"], second["sha256"])
        self.assertNotEqual(second["sha256"], third["sha256"])
        self.assertEqual(third["files"]["example.py"], "deleted")

    def test_inventory_order_and_duplicate_entries_do_not_change_fingerprint(self):
        (self.root / "one.py").write_bytes(b"one")
        (self.root / "two.py").write_bytes(b"two")
        self.assertEqual(self.snapshot(["one.py", "two.py"])["sha256"],
                         self.snapshot(["two.py", "one.py", "one.py"])["sha256"])

    def test_reporting_commit_does_not_invalidate_unchanged_source(self):
        (self.root / "source.py").write_bytes(b"source")
        (self.root / "evidence").mkdir()
        (self.root / "evidence/report.json").write_text("{}", encoding="utf-8")
        (self.root / "docs").mkdir()
        (self.root / "docs/resultats.md").write_text("Résultats", encoding="utf-8")
        a = self.snapshot(["source.py"])
        b = self.snapshot(["source.py", "evidence/report.json", "docs/resultats.md"])
        self.assertEqual(a["sha256"], b["sha256"])


class EvidenceStatusTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="t3l4n-test-evidence-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root_patch = patch.object(bridge, "ROOT", self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.claim = {"id": "TEST-01", "statement": "Les deux nœuds locaux répondent.",
                      "scope": "Infrastructure seulement", "hypotheses": ["Docker disponible"],
                      "code": ["scripts/bridge.py"], "verification": "startup", "environment": "local-fast",
                      "expected": "31337 et 31338", "status": "vérifié_local",
                      "evidence": "evidence/campaign/manifest.json"}
        self.snapshot = {"sha256": hashlib.sha256(b"source fixture").hexdigest()}
        self.manifest = {"source": self.snapshot, "profile": "local-fast", "passed": True,
                         "claim_definitions": {"TEST-01": bridge.digest(bridge.canonical(bridge.claim_definition(self.claim)))},
                         "checks": [{"id": "startup", "passed": True}, {"id": "source_unchanged", "passed": True}], "artifacts": {}}
        self.path = self.root / self.claim["evidence"]
        self.save()

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.manifest, ensure_ascii=False), encoding="utf-8")
        self.path.with_suffix(".sha256").write_text(hashlib.sha256(self.path.read_bytes()).hexdigest() + "  manifest.json\n", encoding="utf-8")

    def status(self, claim=None):
        return bridge.effective_status(claim or self.claim, self.snapshot)

    def test_matching_claim_and_passing_evidence_preserve_verified_status(self):
        self.assertEqual(self.status(), "vérifié_local")

    def test_failed_campaign_cannot_validate_an_individually_passing_check(self):
        self.manifest["passed"] = False
        self.manifest["checks"].append({"id": "mandatory_test", "passed": False})
        self.save()
        self.assertEqual(self.status(), "obsolète")

    def test_unstable_campaign_stays_obsolete_when_checkout_returns_to_initial_sources(self):
        self.manifest["passed"] = False
        self.manifest["checks"][-1]["passed"] = False
        self.save()
        self.assertEqual(bridge.effective_status(self.claim, {"sha256": "changed_during_campaign"}), "obsolète")
        self.assertEqual(bridge.effective_status(self.claim, deepcopy(self.snapshot)), "obsolète")

    def test_missing_or_failed_source_stability_check_invalidates_success_flag(self):
        for check in (None, {"id": "source_unchanged", "passed": False}):
            with self.subTest(check=check):
                self.manifest["checks"] = [{"id": "startup", "passed": True}] + ([check] if check else [])
                self.save()
                self.assertEqual(self.status(), "obsolète")

    def test_besu_claim_accepts_only_its_matching_besu_evidence(self):
        self.claim["environment"] = "local-besu"
        self.claim["status"] = "vérifié_besu_local"
        self.manifest["profile"] = "local-besu"
        self.manifest["claim_definitions"]["TEST-01"] = bridge.digest(bridge.canonical(bridge.claim_definition(self.claim)))
        self.save()
        self.assertEqual(self.status(), "vérifié_besu_local")

    def test_changed_source_makes_previous_evidence_obsolete(self):
        changed = {"sha256": hashlib.sha256(b"changed source").hexdigest()}
        self.assertEqual(bridge.effective_status(self.claim, changed), "obsolète")

    def test_changed_assertion_scope_requires_a_new_verification(self):
        claim = deepcopy(self.claim)
        claim["scope"] = "Transfert ERC20 aller-retour"
        self.assertEqual(self.status(claim), "obsolète")

    def test_failure_or_missing_check_never_counts_as_verified(self):
        for checks in ([{"id": "startup", "passed": False}], [], [{"id": "other", "passed": True}]):
            with self.subTest(checks=checks):
                self.manifest["checks"] = checks
                self.save()
                self.assertEqual(self.status(), "obsolète")

    def test_missing_proof_never_counts_as_verified(self):
        self.path.unlink()
        self.assertEqual(self.status(), "obsolète")
        without_reference = deepcopy(self.claim)
        without_reference["evidence"] = None
        self.assertEqual(self.status(without_reference), "obsolète")

    def test_local_proof_cannot_be_labelled_tela_or_besu(self):
        for status in ("vérifié_tela", "vérifié_sepolia", "vérifié_besu_local"):
            with self.subTest(status=status):
                claim = deepcopy(self.claim)
                claim["status"] = status
                self.assertEqual(self.status(claim), "obsolète")

    def test_manifest_from_different_profile_is_not_reused(self):
        self.manifest["profile"] = "local-besu"
        self.save()
        self.assertEqual(self.status(), "obsolète")

    def test_manifest_tampering_invalidates_integrity(self):
        self.path.write_text(self.path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        self.assertEqual(self.status(), "obsolète")

    def test_missing_or_changed_artifact_invalidates_integrity(self):
        artifact = self.path.parent / "commands.json"
        artifact.write_bytes(b"[]")
        self.manifest["artifacts"] = {"commands.json": hashlib.sha256(b"[]").hexdigest()}
        self.save()
        self.assertEqual(self.status(), "vérifié_local")
        artifact.write_bytes(b"[{}]")
        self.assertEqual(self.status(), "obsolète")
        artifact.unlink()
        self.assertEqual(self.status(), "obsolète")

    def test_missing_checksum_or_invalid_json_is_not_verification(self):
        self.path.with_suffix(".sha256").unlink()
        self.assertEqual(self.status(), "obsolète")
        self.path.write_bytes(b"not a JSON manifest")
        self.path.with_suffix(".sha256").write_text(hashlib.sha256(self.path.read_bytes()).hexdigest() + "  manifest.json\n", encoding="utf-8")
        self.assertEqual(self.status(), "obsolète")

    def test_incomplete_manifest_with_valid_checksum_is_obsolete(self):
        original = deepcopy(self.manifest)
        for missing in ("source", "checks", "claim_definitions", "profile", "artifacts", "passed"):
            with self.subTest(missing=missing):
                self.manifest = deepcopy(original)
                del self.manifest[missing]
                self.save()
                self.assertEqual(self.status(), "obsolète")

    def test_manifest_reference_cannot_leave_the_repository(self):
        with tempfile.TemporaryDirectory(prefix="t3l4n-test-outside-proof-") as d:
            self.path = Path(d) / "manifest.json"
            self.save()
            claim = deepcopy(self.claim)
            claim["evidence"] = str(self.path)
            self.assertEqual(self.status(claim), "obsolète")

    def test_artifact_reference_cannot_leave_its_campaign(self):
        artifact = self.path.parent.parent / "outside.txt"
        artifact.write_bytes(b"public test witness")
        self.manifest["artifacts"] = {"../outside.txt": hashlib.sha256(artifact.read_bytes()).hexdigest()}
        self.save()
        self.assertEqual(self.status(), "obsolète")

    def test_unverified_claim_is_not_promoted_by_an_existing_manifest(self):
        for status in ("proposé", "implémenté", "bloqué"):
            with self.subTest(status=status):
                claim = deepcopy(self.claim)
                claim["status"] = status
                self.assertEqual(self.status(claim), status)


class RegistryReferenceTests(unittest.TestCase):
    def test_nonexistent_code_reference_fails_lint(self):
        claim = {"id": "TEST-01", "statement": "Assertion test", "scope": "local", "hypotheses": [],
                 "code": ["file-that-does-not-exist-for-test.py"], "verification": "startup",
                 "environment": "local-fast", "expected": "attendu", "status": "proposé"}
        with patch.object(bridge, "registry", return_value={"claims": [claim]}), self.assertRaises(bridge.BridgeError):
            bridge.lint()

    def test_existing_code_reference_is_accepted(self):
        claim = {"id": "TEST-01", "statement": "Assertion test", "scope": "local", "hypotheses": [],
                 "code": ["scripts/bridge.py"], "verification": "startup",
                 "environment": "local-fast", "expected": "attendu", "status": "proposé"}
        with patch.object(bridge, "registry", return_value={"claims": [claim]}), redirect_stdout(io.StringIO()):
            bridge.lint()


class CleanupBoundaryTests(unittest.TestCase):
    def test_down_keeps_volumes_and_selects_only_the_requested_project(self):
        for name in ("local-fast", "local-besu"):
            with self.subTest(profile=name), tempfile.TemporaryDirectory(prefix="t3l4n-test-compose-") as d:
                with patch.object(bridge, "LOCAL", Path(d)), patch.object(bridge, "run", return_value={"exit_code": 0, "stdout": ""}) as run, patch.object(bridge, "status") as status, patch.object(bridge.sys, "argv", ["bridge", "down", "--profile", name]):
                    self.assertEqual(bridge.main(), 0)
                    run.assert_called_once()
                    command = [str(x) for x in run.call_args.args[0]]
                    self.assertEqual(command[:2], ["docker", "compose"])
                    self.assertEqual(command[command.index("--project-name") + 1], "t3l4n-bridge-" + name)
                    self.assertIn("down", command)
                    for forbidden in ("--volumes", "-v", "--rmi", "prune"):
                        self.assertNotIn(forbidden, command)
                    status.assert_called_once_with(name)

    def test_compose_environment_cannot_redirect_project_or_config(self):
        injected = {"COMPOSE_PROJECT_NAME": "unrelated-project", "COMPOSE_FILE": "unrelated.yaml", "COMPOSE_PROFILES": "unsafe"}
        with tempfile.TemporaryDirectory(prefix="t3l4n-test-compose-") as d, patch.object(bridge, "LOCAL", Path(d)), patch.dict(os.environ, injected), patch.object(bridge, "run", return_value={"exit_code": 0}) as run:
            bridge.compose("local-fast", ["down"])
            command = [str(x) for x in run.call_args.args[0]]
            env = run.call_args.kwargs["env"]
            self.assertEqual(command[command.index("--project-name") + 1], "t3l4n-bridge-local-fast")
            self.assertFalse(any(k.startswith("COMPOSE_") for k in env))
            self.assertNotIn("unrelated.yaml", command)


class RpcIdentityTests(unittest.TestCase):
    def test_rpc_rejects_mismatched_id_errors_and_missing_result(self):
        for payload in ({"id": 2, "result": "0x1"}, {"id": 1, "error": {"code": -32000, "message": "test"}}, {"id": 1}):
            with self.subTest(payload=payload), patch.object(bridge.urllib.request, "build_opener") as factory:
                factory.return_value.open.return_value = io.BytesIO(json.dumps(payload).encode("utf-8"))
                with self.assertRaises(bridge.BridgeError):
                    bridge.rpc("http://127.0.0.1:18545", "eth_chainId")

    def test_rpc_keeps_response_result_without_sending_transactions(self):
        with patch.object(bridge.urllib.request, "build_opener") as factory:
            factory.return_value.open.return_value = io.BytesIO(b'{"jsonrpc":"2.0","id":1,"result":"0x7a69"}')
            self.assertEqual(bridge.rpc("http://127.0.0.1:18545", "eth_chainId"), "0x7a69")
            request = factory.return_value.open.call_args.args[0]
            self.assertEqual(request.full_url, "http://127.0.0.1:18545")
            self.assertEqual(json.loads(request.data)["method"], "eth_chainId")

    def test_wrong_chain_identity_is_rejected_before_reading_blocks(self):
        chain = read_profile()["chains"][0]
        with patch.object(bridge, "rpc", side_effect=["0x1", "anvil/test"]) as rpc:
            with self.assertRaises(bridge.BridgeError):
                bridge.chain_observation(chain)
            self.assertEqual(rpc.call_count, 2)

    def test_wrong_client_is_rejected_before_reading_blocks(self):
        chain = read_profile()["chains"][0]
        with patch.object(bridge, "rpc", side_effect=[hex(chain["chain_id"]), "other/test"]) as rpc:
            with self.assertRaises(bridge.BridgeError):
                bridge.chain_observation(chain)
            self.assertEqual(rpc.call_count, 2)

    def test_missing_genesis_or_head_is_not_a_healthy_chain(self):
        chain = read_profile()["chains"][0]
        block = {"hash": "0xabc", "number": "0x5"}
        for genesis, head in ((None, block), (block, None)):
            with self.subTest(genesis=genesis, head=head), patch.object(bridge, "rpc", side_effect=[hex(chain["chain_id"]), "anvil/test", genesis, head]):
                with self.assertRaises(bridge.BridgeError):
                    bridge.chain_observation(chain)

    def test_observation_retains_network_and_block_identifiers(self):
        chain = read_profile()["chains"][0]
        with patch.object(bridge, "rpc", side_effect=[hex(chain["chain_id"]), "anvil/test", {"hash": "0xabc", "number": "0x0"}, {"hash": "0xdef", "number": "0x10"}]):
            result = bridge.chain_observation(chain)
        self.assertEqual(result["chain_id"], 31337)
        self.assertEqual(result["genesis_hash"], "0xabc")
        self.assertEqual(result["head_hash"], "0xdef")
        self.assertEqual(result["head"], 16)


if __name__ == "__main__":
    unittest.main()
