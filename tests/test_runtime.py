"""Frontières de l'orchestration du déploiement, sans RPC ni émission de transaction."""
import sys
from pathlib import Path
import unittest
import json
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import bridge
import bridge_runtime as app


class AbiBoundaryTests(unittest.TestCase):
    def test_static_abi_known_layout(self):
        encoded = app.encode(["address", "uint256"], ["0x" + "12" * 20, 42])
        self.assertEqual(encoded, "0" * 24 + "12" * 20 + "0" * 62 + "2a")

    def test_dynamic_string_uses_byte_length_and_padding(self):
        encoded = bytes.fromhex(app.encode(["string", "uint256"], ["é", 7]))
        self.assertEqual(int.from_bytes(encoded[:32], "big"), 64)
        self.assertEqual(int.from_bytes(encoded[32:64], "big"), 7)
        self.assertEqual(int.from_bytes(encoded[64:96], "big"), 2)
        self.assertEqual(encoded[96:], b"\xc3\xa9" + b"\0" * 30)

    def test_amounts_and_addresses_are_not_silently_truncated(self):
        for types, values in [(["uint256"], [-1]), (["uint8"], [256]), (["address"], ["0x01"]),
                              (["uint256"], [2**256]), (["bytes32"], ["0x00"]), (["address"], [])]:
            with self.subTest(values=values), self.assertRaises(ValueError):
                app.encode(types, values)

    def test_prepare_rejects_real_integration_before_key_or_image_access(self):
        with patch.object(app, "image") as image:
            with self.assertRaises(bridge.BridgeError):
                app.prepare(bridge, "integration-testnet")
            image.assert_not_called()


class ApplicationIsolationPolicyTests(unittest.TestCase):
    def test_relayer_cannot_receive_signing_key_even_if_compose_accepts_it(self):
        cfg = {"services": {"relayer": {"user": "1654", "read_only": True, "cap_drop": ["ALL"],
               "security_opt": ["no-new-privileges:true"], "mem_limit": 1, "cpus": 1, "pids_limit": 32,
               "logging": {"driver": "json-file"}, "image": bridge.lock()["images"]["dotnet_runtime"],
               "secrets": [{"source": "key_a"}]}}, "networks": {}}
        with patch.object(bridge, "compose", return_value={"stdout": json.dumps(cfg)}):
            with self.assertRaisesRegex(bridge.BridgeError, "Secret attribué"):
                bridge.validate_compose("local-fast")


class EffectiveHardeningTests(unittest.TestCase):
    def inspect_with(self, security_options):
        raw = [{"Config": {"User": "1654:1654", "Image": "review-fixture"},
                "HostConfig": {"ReadonlyRootfs": True, "Privileged": False, "CapDrop": ["ALL"],
                               "SecurityOpt": security_options, "Memory": 67108864,
                               "NanoCpus": 1000000000, "PidsLimit": 128,
                               "PortBindings": {}, "LogConfig": {"Type": "json-file"}}, "Mounts": []}]
        with patch.object(bridge, "container_id", return_value="fixture-container"), patch.object(bridge, "run", return_value={"stdout": json.dumps(raw)}):
            return bridge.inspect_runtime("local-fast")

    def test_effective_inspection_accepts_documented_enabled_forms(self):
        for option in ("no-new-privileges", "no-new-privileges:true", "no-new-privileges=true"):
            with self.subTest(option=option):
                self.assertIn("relayer", self.inspect_with([option]))

    def test_effective_inspection_rejects_disabled_or_conflicting_options(self):
        for options in ([], ["no-new-privileges:false"], ["no-new-privileges=false"],
                        ["no-new-privileges:0"], ["label:no-new-privileges:true"],
                        ["no-new-privileges:true", "no-new-privileges:false"],
                        ["no-new-privileges=false", "no-new-privileges=true"]):
            with self.subTest(options=options), self.assertRaises(bridge.BridgeError):
                self.inspect_with(options)


class CreationReceiptDomainTests(unittest.TestCase):
    def test_same_contract_address_on_two_chains_does_not_select_the_other_receipt(self):
        address = "0x" + "12" * 20
        a = {"contractAddress": address, "transactionHash": "tx-a", "blockHash": "block-a"}
        b = {"contractAddress": address, "transactionHash": "tx-b", "blockHash": "block-b"}
        def rpc(url, method, params):
            self.assertEqual(url, "rpc-b")
            if params[0] == "tx-a":
                return None
            if method == "eth_getTransactionByHash":
                return {"input": "0x6000abcd"}
            return {**b, "status": "0x1"}
        with patch.object(bridge, "rpc", side_effect=rpc):
            observed = app.creation_on_chain(bridge, {"chain_id": 31338, "rpc_host": "rpc-b"}, address, "0x6000", [a, b])
        self.assertEqual(observed["transactionHash"], "tx-b")
        self.assertEqual(observed["chainId"], 31338)
        self.assertNotIn("chainId", a)

    def test_no_matching_receipt_is_not_a_validation(self):
        with patch.object(bridge, "rpc", return_value=None):
            with self.assertRaises(bridge.BridgeError):
                app.creation_on_chain(bridge, {"chain_id": 31338, "rpc_host": "rpc-b"}, "0x12", "0x6000", [])


if __name__ == "__main__":
    unittest.main()
