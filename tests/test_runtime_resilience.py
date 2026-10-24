"""Refus avant toute injection réseau/SQL de la campagne locale."""
import sys
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bridge
import resilience


class ResilienceBoundaryTests(unittest.TestCase):
    def test_shared_integration_is_rejected_before_process_or_file_access(self):
        with patch.object(bridge, "run") as process, patch.object(bridge, "runtime") as files:
            with self.assertRaises(bridge.BridgeError):
                resilience.run(bridge, "integration-testnet")
            process.assert_not_called()
            files.assert_not_called()

    def test_unknown_or_empty_cases_cannot_mutate_local_services(self):
        for cases in ([], ["not_a_case"], ["pause_resume", "pause_resume"]):
            with self.subTest(cases=cases), patch.object(bridge, "run") as process, patch.object(bridge, "runtime") as files:
                with self.assertRaises(ValueError):
                    resilience.run(bridge, "local-fast", cases)
                process.assert_not_called()
                files.assert_not_called()

    def test_rpc_supplied_transfer_id_cannot_escape_sql_literal(self):
        campaign = resilience.Campaign.__new__(resilience.Campaign)
        campaign.sql = Mock()
        for value in ("' OR true;--", "0x" + "0" * 63, "0x" + "0" * 64 + "'; DELETE FROM bridge.transfers;--"):
            for method in (campaign.row, campaign.counts):
                with self.subTest(value=value, method=method.__name__), self.assertRaises(ValueError):
                    method(value)
        campaign.sql.assert_not_called()


if __name__ == "__main__":
    unittest.main()
