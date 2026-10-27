"""Garde-fous du minage explicite du laboratoire, sans RPC ni conteneur réel."""
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import bridge
import bridge_runtime as rt
sys.path.insert(0, str(Path(__file__).resolve().parent))
import resilience


GENESIS = "0x" + "11" * 32
BLOCK = "0x" + "22" * 32
TX = "0x" + "33" * 32
OTHER = "0x" + "44" * 32


class LocalRpc:
    """Chaîne témoin : seul evm_mine peut modifier sa tête."""
    def __init__(self, chain, head=10):
        self.chain, self.head = chain, head
        self.chain_id, self.client = chain["chain_id"], chain["client_prefix"] + "/fixture"
        self.genesis, self.block_hash = GENESIS, BLOCK
        self.receipt = {"transactionHash": TX, "blockHash": BLOCK, "blockNumber": "0xa", "status": "0x1"}
        self.calls, self.mined = [], 0
        self.on_mine = None

    def __call__(self, url, method, params=None):
        assert url == self.chain["rpc_host"], "RPC vers une destination non attendue"
        self.calls.append((method, deepcopy(params)))
        if method == "eth_chainId":
            return hex(self.chain_id)
        if method == "web3_clientVersion":
            return self.client
        if method == "eth_getBlockByNumber":
            if params[0] == "0x0":
                return {"hash": self.genesis, "number": "0x0"}
            if params[0] == "latest":
                return {"hash": BLOCK, "number": hex(self.head)}
            assert params[0] == "0xa"
            return {"hash": self.block_hash, "number": "0xa"}
        if method == "eth_getTransactionReceipt":
            assert params == [TX]
            return deepcopy(self.receipt)
        if method == "evm_mine":
            self.mined += 1
            self.head += 1
            if self.on_mine:
                self.on_mine(self)
            return "0x0"
        raise AssertionError("RPC inattendu : " + method)


class LocalConfirmationTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix="t3l4n-confirmation-test-")
        self.addCleanup(self.folder.cleanup)
        self.runtime = Path(self.folder.name)
        self.runtime_patch = patch.object(bridge, "runtime", return_value=self.runtime)
        self.runtime_patch.start()
        self.addCleanup(self.runtime_patch.stop)
        self.prepare("local-fast")

    def prepare(self, profile):
        self.profile = profile
        p = bridge.profile(profile, runnable=True)
        self.chain = p["chains"][0]
        self.deployment = {"profile": profile, "networks": [
            {"chainId": c["chain_id"], "genesisHash": GENESIS} for c in p["chains"]]}
        bridge.write_json(self.runtime / "deployment.json", self.deployment)
        self.rpc = LocalRpc(self.chain)
        self.original = dict(self.rpc.receipt, chainId=self.chain["chain_id"])

    def confirm(self, chain=None, original=None):
        with patch.object(bridge, "rpc", side_effect=self.rpc):
            return rt.confirm_local_receipt(bridge, self.profile, chain or self.chain, original or self.original)

    def test_unknown_and_integration_profiles_refuse_before_any_rpc(self):
        for profile in ("mainnet", "unknown", "integration-testnet"):
            with self.subTest(profile=profile), patch.object(bridge, "rpc") as rpc:
                with self.assertRaises(bridge.BridgeError):
                    rt.confirm_local_receipt(bridge, profile, self.chain, self.original)
                rpc.assert_not_called()

    def test_injected_chain_refuses_before_any_rpc(self):
        for field, value in (("rpc_host", "https://example.invalid/rpc"), ("chain_id", 1),
                             ("client_prefix", "besu"), ("finality", {"mode": "confirmations", "depth": 9})):
            with self.subTest(field=field):
                changed = deepcopy(self.chain)
                changed[field] = value
                with self.assertRaises(bridge.BridgeError):
                    self.confirm(chain=changed)
                self.assertEqual(self.rpc.calls, [])

    def test_ambiguous_or_cross_profile_deployment_refuses_before_rpc(self):
        for change in (lambda d: d.update(profile="local-besu"),
                       lambda d: d["networks"].append(deepcopy(d["networks"][0]))):
            with self.subTest(change=change):
                changed = deepcopy(self.deployment)
                change(changed)
                bridge.write_json(self.runtime / "deployment.json", changed)
                with self.assertRaises(bridge.BridgeError):
                    self.confirm()
                self.assertEqual(self.rpc.calls, [])

    def test_invalid_original_receipt_refuses_before_rpc(self):
        for change in ({"chainId": 31338}, {"status": "0x0"}, {"blockNumber": "invalid"},
                       {"transactionHash": "bad"}, {"blockHash": None}):
            with self.subTest(change=change), self.assertRaises(bridge.BridgeError):
                self.confirm(original=dict(self.original, **change))
            self.assertEqual(self.rpc.calls, [])

    def test_wrong_network_identity_cannot_mine(self):
        for attribute, value in (("chain_id", 1), ("client", "other/fixture"), ("genesis", OTHER)):
            with self.subTest(attribute=attribute):
                self.rpc = LocalRpc(self.chain)
                setattr(self.rpc, attribute, value)
                with self.assertRaises(bridge.BridgeError):
                    self.confirm()
                self.assertEqual(self.rpc.mined, 0)

    def test_missing_or_replaced_receipt_cannot_mine(self):
        for actual in (None, dict(self.rpc.receipt, status="0x0"), dict(self.rpc.receipt, transactionHash=OTHER),
                       dict(self.rpc.receipt, blockHash=OTHER), dict(self.rpc.receipt, blockNumber="0x9")):
            with self.subTest(actual=actual):
                self.rpc.receipt = actual
                with self.assertRaises(bridge.BridgeError):
                    self.confirm()
                self.assertEqual(self.rpc.mined, 0)

    def test_noncanonical_block_cannot_mine(self):
        self.rpc.block_hash = OTHER
        with self.assertRaises(bridge.BridgeError):
            self.confirm()
        self.assertEqual(self.rpc.mined, 0)

    def test_head_before_receipt_cannot_mine(self):
        self.rpc.head = 9
        with self.assertRaisesRegex(bridge.BridgeError, "Tête antérieure"):
            self.confirm()
        self.assertEqual(self.rpc.mined, 0)

    def test_three_confirmations_are_explicitly_produced_and_reported(self):
        result = self.confirm()
        self.assertEqual((self.rpc.head, self.rpc.mined), (13, 3))
        self.assertEqual((result["head_before"], result["target"], result["head_after"], result["mined_blocks"]), (10, 13, 13, 3))
        self.assertEqual(result["transaction_hash"], TX)
        self.assertEqual(result["block_hash"], BLOCK)

    def test_already_confirmed_receipt_does_not_mine(self):
        self.rpc.head = 20
        result = self.confirm()
        self.assertEqual(self.rpc.mined, 0)
        self.assertEqual(result["head_after"], 20)

    def test_only_remaining_deficit_is_mined(self):
        self.rpc.head = 12
        self.assertEqual(self.confirm()["mined_blocks"], 1)
        self.assertEqual(self.rpc.head, 13)

    def test_external_progress_does_not_expand_budget(self):
        self.rpc.on_mine = lambda chain: setattr(chain, "head", chain.head + 1)
        result = self.confirm()
        self.assertEqual(result["mined_blocks"], 2)
        self.assertEqual(result["head_after"], 14)

    def test_reorg_after_first_mined_block_refuses_remaining_blocks(self):
        self.rpc.on_mine = lambda chain: setattr(chain, "block_hash", OTHER)
        with self.assertRaisesRegex(bridge.BridgeError, "non canonique"):
            self.confirm()
        self.assertEqual(self.rpc.mined, 1)

    def test_identity_change_after_first_mined_block_refuses_remaining_blocks(self):
        self.rpc.on_mine = lambda chain: setattr(chain, "genesis", OTHER)
        with self.assertRaisesRegex(bridge.BridgeError, "Genesis modifié"):
            self.confirm()
        self.assertEqual(self.rpc.mined, 1)

    def test_no_progress_after_mine_fails_without_looping(self):
        self.rpc.on_mine = lambda chain: setattr(chain, "head", chain.head - 1)
        with self.assertRaisesRegex(bridge.BridgeError, "n'a pas avancé"):
            self.confirm()
        self.assertEqual(self.rpc.mined, 1)

    def test_besu_receipt_is_checked_without_anvil_mining(self):
        self.prepare("local-besu")
        result = self.confirm()
        self.assertEqual(result["mode"], "qbft-local")
        self.assertEqual(result["head_after"], 10)
        self.assertEqual(self.rpc.mined, 0)

    def test_deployment_chooses_last_receipt_from_each_exact_chain(self):
        receipt_a = dict(self.original, blockNumber="0xc")
        receipt_b = dict(self.original, blockNumber="0xb", chainId=31338)
        # Une hauteur plus élevée sans identité ne doit pas gagner la sélection.
        unbound = {k: v for k, v in dict(self.original, blockNumber="0xff").items() if k != "chainId"}
        self.deployment["receipts"] = [self.original, receipt_a, receipt_b, unbound]
        with patch.object(rt, "confirm_local_receipt", return_value={}) as confirm:
            rt.confirm_deployment(bridge, "local-fast", self.deployment)
        self.assertEqual([call.args[3] for call in confirm.call_args_list], [receipt_a, receipt_b])

    def test_deployment_refuses_receipts_not_bound_to_both_chains(self):
        self.deployment["receipts"] = [self.original]
        with patch.object(rt, "confirm_local_receipt", return_value={}) as confirm:
            with self.assertRaisesRegex(bridge.BridgeError, "Aucun reçu"):
                rt.confirm_deployment(bridge, "local-fast", self.deployment)
            confirm.assert_not_called()


class TransferConfirmationWindowTests(unittest.TestCase):
    def test_transfer_can_keep_an_unfinalized_burn_for_reorg_scenario(self):
        # Ici seules les transactions synthétiques du helper sont simulées :
        # la campagne réelle conserve son assertion waiting_finality en base.
        chain = bridge.profile("local-fast")["chains"][0]
        source = {"chainId": 31337, "adminAddress": "0x" + "55" * 20,
                  "tokenAddress": "0x" + "66" * 20, "bridgeAddress": "0x" + "77" * 20}
        destination = dict(source, chainId=31338)
        burn = {"logs": [{"address": source["bridgeAddress"], "topics": [BLOCK, TX]}]}
        real_read = bridge.read_json
        def read(path):
            return {"networks": [source, destination]} if path.name == "deployment.json" else real_read(path)
        for enabled in (False, True):
            with self.subTest(confirm_source=enabled), patch.object(bridge, "runtime", return_value=Path("fixture")), \
                    patch.object(bridge, "read_json", side_effect=read), \
                    patch.object(rt, "transaction", side_effect=[{}, burn]), \
                    patch.object(rt, "calldata", return_value="0x"), patch.object(rt, "keccak", return_value=BLOCK), \
                    patch.object(rt, "confirm_local_receipt", return_value={"mined_blocks": 3}) as confirm:
                result = rt.transfer(bridge, "local-fast", 0, 1, confirm_source=enabled)
                self.assertEqual(result["transfer_id"], TX)
                self.assertEqual(confirm.call_count, int(enabled))
                if enabled:
                    confirm.assert_called_once_with(bridge, "local-fast", chain, burn)


class ReorgMiningRestorationTests(unittest.TestCase):
    class InjectedFailure(RuntimeError):
        pass

    class MiningRpc:
        # Sémantique constatée sur Anvil 1.8.4, et non deux booléens indépendants.
        def __init__(self, auto, interval):
            self.auto, self.interval = auto, interval
            self.mutations = []

        def __call__(self, url, method, params=None):
            if method == "anvil_getAutomine":
                return self.auto
            if method == "anvil_getIntervalMining":
                return self.interval or None
            if method == "eth_blockNumber":
                return "0xa"
            if method == "evm_setIntervalMining":
                self.mutations.append((method, params[0]))
                self.auto, self.interval = False, params[0]
                return None
            if method == "evm_setAutomine":
                self.mutations.append((method, params[0]))
                if params[0]:
                    self.auto, self.interval = True, 0
                elif self.auto:
                    self.auto, self.interval = False, 0
                return None
            raise AssertionError("RPC inattendu : " + method)

    def campaign(self):
        campaign = resilience.Campaign.__new__(resilience.Campaign)
        campaign.b = bridge
        campaign.chains = bridge.profile("local-fast")["chains"]
        campaign.networks = [{}, {}]
        campaign.current = {"checks": []}
        campaign.balance = Mock(side_effect=[500, 700])
        campaign.wait = Mock(side_effect=self.InjectedFailure("défaut injecté avant snapshot"))
        return campaign

    def test_exception_restores_each_supported_mode_and_propagates(self):
        for auto, interval in ((True, 0), (False, 2), (False, 0)):
            with self.subTest(auto=auto, interval=interval):
                rpc = self.MiningRpc(auto, interval)
                campaign = self.campaign()
                with patch.object(bridge, "rpc", side_effect=rpc):
                    with self.assertRaisesRegex(self.InjectedFailure, "défaut injecté"):
                        campaign.reorg_before_finality()
                self.assertEqual((rpc.auto, rpc.interval), (auto, interval))
                self.assertEqual(campaign.current["checks"][-1]["id"], "mining_restored")
                self.assertTrue(campaign.current["checks"][-1]["passed"])

    def test_ambiguous_mixed_mode_refuses_before_mutation(self):
        rpc = self.MiningRpc(True, 2)
        campaign = self.campaign()
        with patch.object(bridge, "rpc", side_effect=rpc):
            with self.assertRaisesRegex(resilience.CaseFailure, "avant modification"):
                campaign.reorg_before_finality()
        self.assertEqual(rpc.mutations, [])
        campaign.balance.assert_not_called()
        campaign.wait.assert_not_called()

    def test_invalid_mode_refuses_before_mutation(self):
        for auto, interval in (("true", 0), (False, -1)):
            with self.subTest(auto=auto, interval=interval):
                rpc = self.MiningRpc(auto, interval)
                with patch.object(bridge, "rpc", side_effect=rpc):
                    with self.assertRaises(resilience.CaseFailure):
                        self.campaign().reorg_before_finality()
                self.assertEqual(rpc.mutations, [])


if __name__ == "__main__":
    unittest.main()
