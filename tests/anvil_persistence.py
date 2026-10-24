#!/usr/bin/env python3
"""Expérience Anvil isolée : état EVM, blocs, reçus, logs et eth_call historique.

N'utilise ni les nœuds actifs ni une clé privée. Les transactions sont émises
par le compte public déverrouillé du nouveau nœud local sans réseau.
Les volumes/conteneurs temporaires portent un nom et un label dédiés.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROJECT = "t3l4n-bridge-anvil-persistence"
TOPIC = "0x" + "11" * 32


def utc():
    return datetime.now(timezone.utc).isoformat()


def counter_creation():
    # calldata vide => retourner slot0; calldata mot32 => écrire slot0 + LOG1.
    write = bytearray.fromhex("3615600057600035806000556000527f" + "11" * 32 + "60206000a100")
    write[3] = len(write)
    runtime = bytes(write) + bytes.fromhex("5b60005460005260206000f3")
    creation = bytes([0x60, len(runtime), 0x60, 12, 0x60, 0, 0x39, 0x60, len(runtime), 0x60, 0, 0xF3]) + runtime
    return "0x" + creation.hex(), "0x" + runtime.hex()


class Experiment:
    def __init__(self, args):
        self.args = args
        self.run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:6]
        self.name = PROJECT + "-" + self.run_id
        self.volume = self.name + "-data"
        self.output = (ROOT / ".local/anvil-persistence" / self.run_id).resolve()
        self.output.mkdir(parents=True, exist_ok=False)
        self.report = {"utc_started": utc(), "run_id": self.run_id, "variant": args.variant, "image": args.image,
                       "chain_id": 31991, "empty_blocks": args.empty_blocks, "restarts": args.restarts, "python_version": sys.version,
                       "commands": [], "stages": [], "assertions": [], "sources": [
                           "https://github.com/foundry-rs/foundry/blob/v1.3.1/crates/anvil/src/eth/backend/mem/mod.rs#L931",
                           "https://github.com/foundry-rs/foundry/blob/v1.3.1/crates/anvil/src/eth/backend/mem/storage.rs#L383",
                           "https://github.com/foundry-rs/foundry/pull/17148"]}
        self.created_container = False
        self.created_volume = False

    def command(self, *args, check=True, timeout=90):
        start = utc()
        result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=timeout)
        self.report["commands"].append({"utc": start, "argv": list(args), "exit_code": result.returncode})
        if check and result.returncode:
            raise RuntimeError(f"command_failed:{args[0]}:{result.returncode}:{result.stderr[:400]}")
        return result

    def rpc(self, method, *params, check=True):
        result = self.command("docker", "exec", "--env", "TOKIO_WORKER_THREADS=2", "--env", "RAYON_NUM_THREADS=2", self.name,
                              "cast", "rpc", "--rpc-url", "http://127.0.0.1:8545", "--raw", method,
                              json.dumps(list(params), separators=(",", ":")), check=False)
        if result.returncode:
            if check:
                raise RuntimeError(f"rpc_failed:{method}:{result.stderr[:300]}")
            return {"rpc_error": result.stderr.strip()[:400]}
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            if check:
                raise RuntimeError(f"rpc_nonjson:{method}")
            return {"rpc_error": "non_json_response"}

    def assert_equal(self, name, observed, expected):
        passed = observed == expected
        self.report["assertions"].append({"name": name, "expected": expected, "observed": observed, "passed": passed})
        return passed

    def wait_ready(self):
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            if self.rpc("eth_chainId", check=False) == hex(31991):
                return
            time.sleep(0.5)
        raise RuntimeError("isolated_anvil_not_ready")

    def receipt(self, tx):
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            result = self.rpc("eth_getTransactionReceipt", tx)
            if result:
                if result["status"] != "0x1":
                    raise RuntimeError("test_transaction_reverted")
                return result
            time.sleep(0.25)
        raise RuntimeError("test_receipt_timeout")

    def snapshot(self, stage, address, transactions, receipts):
        result = {"stage": stage, "utc": utc(), "head": self.rpc("eth_blockNumber"),
                  "code": self.rpc("eth_getCode", address, "latest"),
                  "latest_call": self.rpc("eth_call", {"to": address, "data": "0x"}, "latest", check=False),
                  "historical_calls": {}, "transactions": {}, "receipts": {}, "blocks": {},
                  "logs": self.rpc("eth_getLogs", {"address": address, "fromBlock": "0x0", "toBlock": "latest", "topics": [TOPIC]}, check=False)}
        for index, tx in enumerate(transactions):
            result["transactions"][tx] = self.rpc("eth_getTransactionByHash", tx, check=False)
            result["receipts"][tx] = self.rpc("eth_getTransactionReceipt", tx, check=False)
            height = receipts[index]["blockNumber"]
            result["blocks"][height] = self.rpc("eth_getBlockByNumber", height, False, check=False)
            result["historical_calls"][height] = self.rpc("eth_call", {"to": address, "data": "0x"}, height, check=False)
        self.report["stages"].append(result)
        self.output.joinpath(stage + ".json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        return result

    def copied_state(self, suffix):
        target = self.output / ("state-" + suffix + ".json")
        self.command("docker", "cp", self.name + ":/home/foundry/state.json", str(target))
        state = json.loads(target.read_text(encoding="utf-8"))
        summary = {"sha256": hashlib.sha256(target.read_bytes()).hexdigest(), "bytes": target.stat().st_size,
                   "blocks": len(state.get("blocks", [])), "transactions": len(state.get("transactions", [])),
                   "historical_states": len(state.get("historical_states") or []), "best_block_number": state.get("best_block_number")}
        self.report.setdefault("state_files", {})[target.name] = summary
        return summary

    def execute(self):
        try:
            self.report["git_commit"] = self.command("git", "rev-parse", "HEAD").stdout.strip()
            self.report["git_status"] = self.command("git", "status", "--porcelain", "--untracked-files=normal").stdout.splitlines()
            self.report["test_sha256"] = hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()
            self.output.joinpath("tested-script.py").write_bytes(pathlib.Path(__file__).read_bytes())
            self.report["image_details"] = json.loads(self.command("docker", "image", "inspect", self.args.image, "--format", "{{json .}}").stdout)
            # Image inspect includes public image defaults only; remove environment clutter.
            image = self.report.pop("image_details")
            self.report["image_details"] = {"id": image["Id"], "repo_digests": image.get("RepoDigests", [])}
            self.command("docker", "volume", "create", "--label", "project=" + PROJECT, "--label", "probe_run=" + self.run_id, self.volume)
            self.created_volume = True
            flags = []
            if self.args.variant in ("history", "keeper"):
                flags += ["--preserve-historical-states"]
            if self.args.variant == "keeper":
                flags += ["--transaction-block-keeper", "3"]
            self.command("docker", "run", "--detach", "--name", self.name, "--label", "project=" + PROJECT, "--label", "probe_run=" + self.run_id,
                         "--network", "none", "--user", "1000:1000", "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
                         "--memory", "384m", "--cpus", "1", "--pids-limit", "128", "--tmpfs", "/tmp:rw,noexec,nosuid,size=32m,mode=1777",
                         "--log-opt", "max-size=2m", "--log-opt", "max-file=2", "--mount", "type=volume,source=" + self.volume + ",target=/home/foundry",
                         "--entrypoint", "anvil", self.args.image, "--quiet", "--host", "127.0.0.1", "--chain-id", "31991", "--hardfork", "london",
                         "--timestamp", "1700000000", "--threads", "2", "--state", "/home/foundry/state.json", "--state-interval", "10", *flags)
            self.created_container = True
            self.wait_ready()
            self.report["anvil_version"] = self.command("docker", "exec", self.name, "anvil", "--version").stdout.strip()
            account = self.rpc("eth_accounts")[0]
            creation, runtime = counter_creation()
            transactions = [self.rpc("eth_sendTransaction", {"from": account, "data": creation, "gas": "0xf4240"})]
            receipts = [self.receipt(transactions[0])]
            address = receipts[0]["contractAddress"]
            for value in (11, 22):
                transactions.append(self.rpc("eth_sendTransaction", {"from": account, "to": address, "data": "0x" + f"{value:064x}", "gas": "0x186a0"}))
                receipts.append(self.receipt(transactions[-1]))
            self.rpc("anvil_mine", hex(self.args.empty_blocks))
            before = self.snapshot("before", address, transactions, receipts)
            self.assert_equal("before_code", before["code"], runtime)
            self.assert_equal("before_latest_call", before["latest_call"], "0x" + f"{22:064x}")
            self.assert_equal("before_log_count", len(before["logs"]) if isinstance(before["logs"], list) else None, 2)
            for index, tx in enumerate(transactions):
                self.assert_equal("before_receipt_" + str(index), before["receipts"][tx], receipts[index])
                found = before["transactions"][tx]
                self.assert_equal("before_transaction_hash_" + str(index), found.get("hash") if isinstance(found, dict) else None, tx)
                self.assert_equal("before_historical_call_" + str(index), before["historical_calls"][receipts[index]["blockNumber"]], "0x" + f"{(0, 11, 22)[index]:064x}")
            for cycle in range(1, self.args.restarts + 1):
                self.command("docker", "stop", "--time", "30", self.name)
                self.report.setdefault("stops", []).append(json.loads(self.command("docker", "inspect", self.name, "--format", "{{json .State}}").stdout))
                self.copied_state(str(cycle))
                self.command("docker", "start", self.name)
                self.wait_ready()
                after = self.snapshot("after-" + str(cycle), address, transactions, receipts)
                prefix = "restart_" + str(cycle) + "_"
                self.assert_equal(prefix + "code", after["code"], runtime)
                self.assert_equal(prefix + "latest_call", after["latest_call"], "0x" + f"{22:064x}")
                self.assert_equal(prefix + "head", after["head"], before["head"])
                self.assert_equal(prefix + "log_count", len(after["logs"]) if isinstance(after["logs"], list) else None, 2)
                for index, tx in enumerate(transactions):
                    self.assert_equal(prefix + "receipt_" + str(index), after["receipts"][tx], receipts[index])
                    self.assert_equal(prefix + "transaction_" + str(index), after["transactions"][tx], before["transactions"][tx])
                    height = receipts[index]["blockNumber"]
                    self.assert_equal(prefix + "historical_call_" + str(index), after["historical_calls"][height], "0x" + f"{(0, 11, 22)[index]:064x}")
                    self.assert_equal(prefix + "block_hash_" + str(index), after["blocks"][height].get("hash"), receipts[index]["blockHash"])
            self.report["completed"] = True
        except Exception as error:
            self.report["completed"] = False
            self.report["error"] = str(error)
        finally:
            # Scope cleanup by exact generated name AND project/run labels; no global prune.
            for created, kind, name, cleanup_command in (
                (self.created_container, "container", self.name, ["docker", "rm", "--force", self.name]),
                (self.created_volume, "volume", self.volume, ["docker", "volume", "rm", self.volume]),
            ):
                if created:
                    try:
                        self.cleanup(kind, name, cleanup_command)
                    except Exception as error:
                        self.report.setdefault("cleanup_errors", []).append({"name": name, "error_type": type(error).__name__})
            self.report["utc_finished"] = utc()
            self.report["passed"] = self.report.get("completed", False) and all(a["passed"] for a in self.report["assertions"]) and not self.report.get("cleanup_errors") and not self.report.get("cleanup_refused")
            self.output.joinpath("report.json").write_text(json.dumps(self.report, indent=2), encoding="utf-8")
            self.output.joinpath("SHA256SUMS").write_text("".join(hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name + "\n" for p in sorted(self.output.iterdir()) if p.is_file() and p.name != "SHA256SUMS"), encoding="utf-8")
            print(json.dumps({"report": str(self.output / "report.json"), "completed": self.report.get("completed"), "passed": self.report["passed"],
                              "failed_assertions": [a["name"] for a in self.report["assertions"] if not a["passed"]], "error": self.report.get("error")}, indent=2), flush=True)
        return 0 if self.report["passed"] else 1

    def cleanup(self, kind, name, command):
        result = self.command("docker", kind, "inspect", name, "--format", "{{json .Config.Labels}}" if kind == "container" else "{{json .Labels}}", check=False)
        labels = json.loads(result.stdout) if result.returncode == 0 else {}
        if labels.get("project") == PROJECT and labels.get("probe_run") == self.run_id:
            self.command(*command)
        else:
            self.report.setdefault("cleanup_refused", []).append(name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=("baseline", "history", "keeper"), default="baseline")
    parser.add_argument("--empty-blocks", type=int, default=12)
    parser.add_argument("--restarts", type=int, default=2)
    images = json.loads((ROOT / "sandbox/versions.lock.json").read_text(encoding="utf-8"))["images"]
    parser.add_argument("--image", default=images.get("anvil", images["foundry"]))
    args = parser.parse_args()
    if not 0 <= args.empty_blocks <= 5000 or not 1 <= args.restarts <= 4 or not args.image.startswith("ghcr.io/foundry-rs/foundry:"):
        parser.error("Bounded local probe parameters required")
    return Experiment(args).execute()


if __name__ == "__main__":
    sys.exit(main())
