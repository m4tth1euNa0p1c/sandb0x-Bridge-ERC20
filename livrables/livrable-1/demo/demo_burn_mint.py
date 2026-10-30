#!/usr/bin/env python3
"""Démonstration ponctuelle du protocole burn/mint v1 sur deux Anvil locaux.

Le relayer est joué pas à pas par ce script (lecture des logs, contrôle de l'ID,
soumission par le compte exécuteur). Il ne remplace ni le relayer .NET, ni la
campagne `prove`. Aucune connexion à Sepolia ou TELA ; comptes Anvil locaux uniquement.
Les clés privées sont lues dans un fichier temporaire hors dépôt et jamais écrites.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
CHAIN_A, CHAIN_B = 31337, 31338
PORT_A, PORT_B = 28545, 28546
UNIT = 10**18
MAX_TRANSFER, EPOCH_CAP, EPOCH_SECONDS = 1_000 * UNIT, 100_000 * UNIT, 3_600
REFERENCE_SUPPLY = 1_000_000 * UNIT
EVENT = "TransferInitiated(bytes32,uint256,address,address,address,address,address,uint256,uint256)"
COMPLETE = "completeTransfer(uint256,address,address,uint256,uint256,address)"
ERRORS = ["TransferAlreadyProcessed(bytes32)", "AccessControlUnauthorizedAccount(address,bytes32)",
          "InvalidAmount(uint256)", "EnforcedPause()", "EpochMintCapExceeded(uint256,uint256)"]


def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Demo:
    def __init__(self, tools, solc, out):
        self.tools, self.solc, self.out = Path(tools), Path(solc), Path(out)
        self.steps, self.checks, self.keys, self.addr, self.events = [], [], {}, {}, []
        self.rpc_url = {CHAIN_A: f"http://127.0.0.1:{PORT_A}", CHAIN_B: f"http://127.0.0.1:{PORT_B}"}

    # --- outils -----------------------------------------------------------------------------
    def run(self, args, *, redact=(), check=True):
        shown = [("<clé locale Anvil masquée>" if a in redact else a) for a in args]
        shown = [Path(a).name if a.startswith("/") else a for a in shown]
        started = utc()
        p = subprocess.run(args, capture_output=True, text=True, timeout=120)
        record = {"utc": started, "command": shown, "exit_code": p.returncode}
        if p.returncode and check:
            record["stderr"] = p.stderr[-600:]
            self.steps.append(record)
            raise RuntimeError(f"échec : {' '.join(shown)}\n{p.stderr}")
        return p, record

    def cast(self, *args, redact=(), check=True):
        return self.run([str(self.tools / "cast"), *args], redact=redact, check=check)

    def rpc(self, chain, method, params=()):
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": list(params)}).encode()
        req = urllib.request.Request(self.rpc_url[chain], body, {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            answer = json.loads(r.read())
        if "error" in answer:
            raise RuntimeError(f"{method}: {answer['error']}")
        return answer["result"]

    def check(self, name, observed, expected):
        ok = observed == expected
        self.checks.append({"utc": utc(), "check": name, "observed": str(observed), "expected": str(expected),
                            "result": "réussi" if ok else "échec"})
        print(("  [OK] " if ok else "  [ÉCHEC] ") + name, flush=True)
        return ok

    # --- chaîne ---------------------------------------------------------------------------
    def send(self, chain, who, to, sig, *values, label, gas=None):
        args = ["send", "--rpc-url", self.rpc_url[chain], "--private-key", self.keys[who], "--json", to, sig,
                *[str(v) for v in values]]
        if gas:
            args[1:1] = ["--gas-limit", str(gas)]
        p, record = self.cast(*args, redact=(self.keys[who],))
        receipt = json.loads(p.stdout)
        record.update({"label": label, "chain_id": chain, "from_role": who, "transactionHash": receipt["transactionHash"],
                       "blockNumber": int(receipt["blockNumber"], 16), "gasUsed": int(receipt["gasUsed"], 16),
                       "status": int(receipt["status"], 16)})
        self.steps.append(record)
        return receipt

    def deploy(self, chain, who, artifact, ctor, *values, label):
        bytecode = json.loads(Path(artifact).read_text())["bytecode"]["object"]
        p, _ = self.cast("abi-encode", ctor, *[str(v) for v in values])
        p, record = self.cast("send", "--rpc-url", self.rpc_url[chain], "--private-key", self.keys[who], "--json",
                              "--create", bytecode + p.stdout.strip()[2:], redact=(self.keys[who],))
        receipt = json.loads(p.stdout)
        record["command"] = record["command"][:-1] + ["<bytecode " + Path(artifact).stem + " + arguments>"]
        record.update({"label": label, "chain_id": chain, "from_role": who, "transactionHash": receipt["transactionHash"],
                       "contractAddress": receipt["contractAddress"], "status": int(receipt["status"], 16),
                       "gasUsed": int(receipt["gasUsed"], 16)})
        self.steps.append(record)
        return receipt["contractAddress"]

    def call(self, chain, to, sig, *values):
        p, _ = self.cast("call", "--rpc-url", self.rpc_url[chain], to, sig, *[str(v) for v in values])
        return p.stdout.strip().split()[0]

    def revert_of(self, chain, who, to, sig, *values):
        """Simule l'appel et renvoie le nom de l'erreur personnalisée, sans rien diffuser."""
        p, _ = self.cast("calldata", sig, *[str(v) for v in values])
        try:
            self.rpc(chain, "eth_call", [{"from": self.addr[who], "to": to, "data": p.stdout.strip()}, "latest"])
            return "aucune erreur"
        except RuntimeError as exc:
            text = str(exc)
        for error in ERRORS:
            selector, _ = self.cast("sig", error)
            if selector.stdout.strip()[2:] in text:
                return error.split("(")[0]
        return "erreur non reconnue"

    def supplies(self):
        a = int(self.call(CHAIN_A, self.addr["erc20A"], "totalSupply()(uint256)"))
        b = int(self.call(CHAIN_B, self.addr["erc20B"], "totalSupply()(uint256)"))
        return a, b

    def transfer_event(self, chain, bridge, receipt):
        topic0 = self.cast("keccak", EVENT)[0].stdout.strip()
        block = int(receipt["blockNumber"], 16)
        logs = self.rpc(chain, "eth_getLogs", [{"fromBlock": hex(block), "toBlock": hex(block), "address": bridge,
                                                "topics": [topic0]}])
        log = [x for x in logs if x["transactionHash"] == receipt["transactionHash"]]
        if len(log) != 1:
            raise RuntimeError("événement TransferInitiated introuvable ou ambigu")
        words = [log[0]["data"][2 + 64 * i: 2 + 64 * (i + 1)] for i in range(6)]
        return {"transferId": log[0]["topics"][1], "destinationChainId": int(log[0]["topics"][2], 16),
                "sender": "0x" + log[0]["topics"][3][-40:], "recipient": "0x" + words[0][-40:],
                "sourceErc20": "0x" + words[1][-40:], "destinationErc20": "0x" + words[2][-40:],
                "destinationBridge": "0x" + words[3][-40:], "nonce": int(words[4], 16), "amount": int(words[5], 16),
                "blockNumber": block, "blockHash": log[0]["blockHash"], "logIndex": int(log[0]["logIndex"], 16)}

    def offchain_id(self, src, src_bridge, dst, dst_bridge, src_erc20, dst_erc20, nonce, amount, recipient):
        domain = self.cast("keccak", "T3L4N_BRIDGE_BURN_MINT")[0].stdout.strip()
        encoded = self.cast("abi-encode",
                            "f(bytes32,uint256,uint256,address,uint256,address,address,address,uint256,uint256,address)",
                            domain, "1", str(src), src_bridge, str(dst), dst_bridge, src_erc20, dst_erc20, str(nonce),
                            str(amount), recipient)[0].stdout.strip()
        return self.cast("keccak", encoded)[0].stdout.strip()

    def wait_confirmations(self, chain, block, depth=3):
        """Convention locale : head - bloc >= 3. Pas une finalité Sepolia ni TELA."""
        self.rpc(chain, "anvil_mine", [hex(depth)])
        head = int(self.rpc(chain, "eth_blockNumber"), 16)
        self.steps.append({"utc": utc(), "label": f"confirmations locales chaîne {chain}", "chain_id": chain,
                           "command": ["rpc", "anvil_mine", str(depth)], "exit_code": 0, "head": head,
                           "inclusion_block": block})
        return head - block

    def relay(self, src, dst, src_bridge, dst_bridge, receipt, label):
        """Relayer joué manuellement : finalité locale, lecture du log, recalcul de l'ID, mint."""
        event = self.transfer_event(src, src_bridge, receipt)
        self.check(f"{label} : {self.wait_confirmations(src, event['blockNumber'])} blocs successeurs ≥ 3", True, True)
        recomputed = self.offchain_id(src, src_bridge, dst, dst_bridge, event["sourceErc20"],
                                      event["destinationErc20"], event["nonce"], event["amount"], event["recipient"])
        self.check(f"{label} : ID recalculé hors chaîne = ID de l'événement", recomputed, event["transferId"])
        source_erc20 = event["sourceErc20"]
        mint = self.send(dst, "executor", dst_bridge, COMPLETE, src, src_bridge, source_erc20, event["nonce"],
                         event["amount"], event["recipient"], label=f"{label} : completeTransfer (mint)")
        self.check(f"{label} : transaction de mint réussie", int(mint["status"], 16), 1)
        processed = self.call(dst, dst_bridge, "processed(bytes32)(bool)", event["transferId"])
        self.check(f"{label} : processed[ID] = true", processed, "true")
        self.events.append({"label": label, "source_chain": src, "burnTransaction": receipt["transactionHash"],
                            "mintTransaction": mint["transactionHash"], "mintBlock": int(mint["blockNumber"], 16),
                            **event})
        return event, mint

    # --- scénario -------------------------------------------------------------------------
    def execute(self):
        work = Path(tempfile.mkdtemp(prefix="t3l4n-demo-"))
        nodes = []
        try:
            print("Compilation des contrats (copie temporaire)", flush=True)
            shutil.copytree(ROOT / "contracts", work / "contracts",
                            ignore=shutil.ignore_patterns("out", "cache", ".toolchain", ".artifacts"))
            build, record = self.run([str(self.tools / "forge"), "build", "--root", str(work / "contracts"),
                                      "--use", str(self.solc), "--offline"])
            record["label"] = "forge build (London, solc 0.8.30)"
            self.steps.append(record)
            print("Tests Solidity (unitaires, fuzzing, invariants)", flush=True)
            tests, record = self.run([str(self.tools / "forge"), "test", "--root", str(work / "contracts"),
                                      "--use", str(self.solc), "--offline", "--fuzz-seed", "0x20261024"], check=False)
            (self.out / "forge-test.log").write_text(tests.stdout + tests.stderr, encoding="utf-8")
            summary = [line for line in tests.stdout.splitlines() if line.startswith("Ran ") and "test suites" in line]
            record.update({"label": "forge test (27 tests attendus)", "summary": summary[-1] if summary else ""})
            self.steps.append(record)
            self.check("tests Solidity : code de sortie", tests.returncode, 0)
            self.check("tests Solidity : 27 réussis, 0 échec, 0 ignoré", "27 tests passed, 0 failed, 0 skipped" in
                       (summary[-1] if summary else ""), True)
            out = work / "contracts/out"
            for chain, port in ((CHAIN_A, PORT_A), (CHAIN_B, PORT_B)):
                cfg = work / f"anvil-{chain}.json"
                nodes.append(subprocess.Popen([str(self.tools / "anvil"), "--host", "127.0.0.1", "--port", str(port),
                                               "--chain-id", str(chain), "--hardfork", "london", "--no-cors",
                                               "--quiet", "--config-out", str(cfg)],
                                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
            for chain in (CHAIN_A, CHAIN_B):
                for _ in range(100):
                    try:
                        self.check(f"identité chaîne {chain}", int(self.rpc(chain, "eth_chainId"), 16), chain)
                        break
                    except OSError:
                        time.sleep(0.1)
            accounts = json.loads((work / f"anvil-{CHAIN_A}.json").read_text())
            for i, role in enumerate(("admin", "pauser", "executor", "alice", "bob")):
                self.keys[role] = accounts["private_keys"][i]
                self.addr[role] = self.cast("wallet", "address", "--private-key", self.keys[role],
                                            redact=(self.keys[role],))[0].stdout.strip()

            print("Déploiement : jetons de test et bridges", flush=True)
            token_art, bridge_art = out / "BridgeToken.sol/BridgeToken.json", out / "Bridge.sol/Bridge.json"
            ctor_t = "constructor(string,string,address,address,uint256)"
            ctor_b = "constructor(address,address,address,address,uint256,uint256,uint256)"
            self.addr["erc20A"] = self.deploy(CHAIN_A, "admin", token_art, ctor_t, "Jeton euro de test", "tEUR",
                                              self.addr["admin"], self.addr["alice"], REFERENCE_SUPPLY,
                                              label="déploiement jeton A")
            self.addr["erc20B"] = self.deploy(CHAIN_B, "admin", token_art, ctor_t, "Jeton euro de test", "tEUR",
                                              self.addr["admin"], self.addr["admin"], 0, label="déploiement jeton B")
            for chain, erc20, name in ((CHAIN_A, "erc20A", "bridgeA"), (CHAIN_B, "erc20B", "bridgeB")):
                self.addr[name] = self.deploy(chain, "admin", bridge_art, ctor_b, self.addr[erc20], self.addr["admin"],
                                              self.addr["pauser"], self.addr["executor"], MAX_TRANSFER, EPOCH_CAP,
                                              EPOCH_SECONDS, label=f"déploiement {name}")
                role = self.call(chain, self.addr[erc20], "BRIDGE_ROLE()(bytes32)")
                self.send(chain, "admin", self.addr[erc20], "grantRole(bytes32,address)", role, self.addr[name],
                          label=f"BRIDGE_ROLE accordé à {name}")
            self.send(CHAIN_A, "admin", self.addr["bridgeA"], "configurePair(uint256,address,address,uint8)", CHAIN_B,
                      self.addr["bridgeB"], self.addr["erc20B"], 18, label="paire A→B (définitive)")
            self.send(CHAIN_B, "admin", self.addr["bridgeB"], "configurePair(uint256,address,address,uint8)", CHAIN_A,
                      self.addr["bridgeA"], self.addr["erc20A"], 18, label="paire B→A (définitive)")
            self.check("offre initiale A + B = référence", sum(self.supplies()), REFERENCE_SUPPLY)

            print("S1 — aller A→B : 100 tEUR", flush=True)
            amount = 100 * UNIT
            self.send(CHAIN_A, "alice", self.addr["erc20A"], "approve(address,uint256)", self.addr["bridgeA"], amount,
                      label="S1 : approve Alice → bridge A")
            burn = self.send(CHAIN_A, "alice", self.addr["bridgeA"], "requestTransfer(uint256,address,uint256)", CHAIN_B,
                             self.addr["bob"], amount, label="S1 : requestTransfer (burn)")
            self.check("S1 : offre A après burn", self.supplies()[0], REFERENCE_SUPPLY - amount)
            self.check("S1 : transit non minté = 100 tEUR", REFERENCE_SUPPLY - sum(self.supplies()), amount)
            event, _ = self.relay(CHAIN_A, CHAIN_B, self.addr["bridgeA"], self.addr["bridgeB"], burn, "S1")
            self.check("S1 : solde Bob sur B", int(self.call(CHAIN_B, self.addr["erc20B"], "balanceOf(address)(uint256)",
                                                             self.addr["bob"])), amount)
            self.check("S1 : offre A + B = référence (transit nul)", sum(self.supplies()), REFERENCE_SUPPLY)

            print("S2 — rejeu du même transfert", flush=True)
            replay_args = (CHAIN_A, self.addr["bridgeA"], event["sourceErc20"], event["nonce"], event["amount"],
                           event["recipient"])
            self.check("S2 : simulation du rejeu refusée",
                       self.revert_of(CHAIN_B, "executor", self.addr["bridgeB"], COMPLETE, *replay_args),
                       "TransferAlreadyProcessed")
            forced = self.send(CHAIN_B, "executor", self.addr["bridgeB"], COMPLETE, *replay_args, gas=300000,
                               label="S2 : rejeu forcé on-chain (gas fixé, sans estimation)")
            self.check("S2 : transaction de rejeu incluse mais annulée (status 0)", int(forced["status"], 16), 0)
            self.check("S2 : aucun second mint", sum(self.supplies()), REFERENCE_SUPPLY)

            print("S3 — exécuteur non autorisé", flush=True)
            self.check("S3 : Alice ne peut pas minter",
                       self.revert_of(CHAIN_B, "alice", self.addr["bridgeB"], COMPLETE, CHAIN_A, self.addr["bridgeA"],
                                      self.addr["erc20A"], 77, UNIT, self.addr["alice"]),
                       "AccessControlUnauthorizedAccount")

            print("S4 — plafond par transfert", flush=True)
            self.check("S4 : 1 001 tEUR refusés",
                       self.revert_of(CHAIN_A, "alice", self.addr["bridgeA"], "requestTransfer(uint256,address,uint256)",
                                      CHAIN_B, self.addr["bob"], 1_001 * UNIT), "InvalidAmount")

            print("S5 — pause d'urgence", flush=True)
            self.send(CHAIN_A, "pauser", self.addr["bridgeA"], "pause()", label="S5 : pause par PAUSER_ROLE")
            self.check("S5 : burn refusé pendant la pause",
                       self.revert_of(CHAIN_A, "alice", self.addr["bridgeA"], "requestTransfer(uint256,address,uint256)",
                                      CHAIN_B, self.addr["bob"], UNIT), "EnforcedPause")
            self.check("S5 : le pauser ne peut pas lever la pause",
                       self.revert_of(CHAIN_A, "pauser", self.addr["bridgeA"], "unpause()"),
                       "AccessControlUnauthorizedAccount")
            self.send(CHAIN_A, "admin", self.addr["bridgeA"], "unpause()", label="S5 : levée de pause par l'admin")
            self.check("S5 : bridge A actif", self.call(CHAIN_A, self.addr["bridgeA"], "paused()(bool)"), "false")

            print("S6 — retour B→A : 40 tEUR", flush=True)
            back = 40 * UNIT
            self.send(CHAIN_B, "bob", self.addr["erc20B"], "approve(address,uint256)", self.addr["bridgeB"], back,
                      label="S6 : approve Bob → bridge B")
            burn_b = self.send(CHAIN_B, "bob", self.addr["bridgeB"], "requestTransfer(uint256,address,uint256)", CHAIN_A,
                               self.addr["alice"], back, label="S6 : requestTransfer (burn)")
            self.relay(CHAIN_B, CHAIN_A, self.addr["bridgeB"], self.addr["bridgeA"], burn_b, "S6")
            a, b = self.supplies()
            self.check("S6 : offre B = 60 tEUR", b, amount - back)
            self.check("S7 : réconciliation offre A + offre B + transit = référence", a + b, REFERENCE_SUPPLY)

            print("S8 — limite de confiance : mint fabriqué par l'exécuteur", flush=True)
            forged = self.send(CHAIN_B, "executor", self.addr["bridgeB"], COMPLETE, CHAIN_A, self.addr["bridgeA"],
                               self.addr["erc20A"], 999, 5 * UNIT, self.addr["executor"],
                               label="S8 : completeTransfer sans burn source (fraude simulée)")
            self.check("S8 : le contrat accepte le mint fabriqué (confiance dans l'exécuteur)",
                       int(forged["status"], 16), 1)
            self.check("S8 : la réconciliation détecte un écart de +5 tEUR", sum(self.supplies()) - REFERENCE_SUPPLY,
                       5 * UNIT)
        finally:
            for node in nodes:
                node.terminate()
                node.wait(timeout=10)
            shutil.rmtree(work, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tools", required=True, help="répertoire contenant forge, anvil et cast")
    parser.add_argument("--solc", required=True, help="binaire solc 0.8.30 vérifié par SHA-256")
    parser.add_argument("--out", required=True, help="répertoire de preuve à créer")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    demo = Demo(args.tools, args.solc, out)
    git = lambda *a: subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    report = {"title": "Démonstration ponctuelle burn/mint v1 sur deux Anvil locaux",
              "scope": "Protocole on-chain et relayer joué manuellement ; ni relayer .NET, ni PostgreSQL, ni Sepolia, ni TELA",
              "started_utc": utc(), "source_commit": git("rev-parse", "HEAD"), "git_status": git("status", "--porcelain"),
              "sources": {p: sha256_file(ROOT / p) for p in ("contracts/src/Bridge.sol", "contracts/src/BridgeToken.sol",
                                                              "livrables/livrable-1/demo/demo_burn_mint.py")},
              "tools": {}}
    for name in ("forge", "anvil", "cast"):
        report["tools"][name] = {"version": subprocess.run([str(Path(args.tools) / name), "--version"], capture_output=True,
                                                           text=True).stdout.splitlines()[0],
                                 "sha256": sha256_file(Path(args.tools) / name)}
    report["tools"]["solc"] = {"sha256": sha256_file(args.solc)}
    exit_code = 0
    try:
        demo.execute()
    except Exception as exc:  # le rapport conserve l'échec, jamais requalifié
        report["error"] = str(exc)[-1000:]
        exit_code = 1
    report.update({"finished_utc": utc(), "chains": {"A": CHAIN_A, "B": CHAIN_B},
                   "addresses": {k: v for k, v in demo.addr.items()},
                   "parameters": {"maxTransfer": str(MAX_TRANSFER), "epochMintCap": str(EPOCH_CAP),
                                  "epochSeconds": EPOCH_SECONDS, "referenceSupply": str(REFERENCE_SUPPLY),
                                  "confirmations": 3, "decimals": 18},
                   "transfers": demo.events, "steps": demo.steps, "checks": demo.checks})
    failed = [c for c in demo.checks if c["result"] != "réussi"]
    report["summary"] = {"checks": len(demo.checks), "passed": len(demo.checks) - len(failed), "failed": len(failed)}
    if failed:
        exit_code = 1
    report["exit_code"] = exit_code
    (out / "demo.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{report['summary']['passed']}/{report['summary']['checks']} contrôles réussis ; code {exit_code}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
