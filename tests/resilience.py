"""Injections de pannes réservées à l'état de test local, sans suppression de données.

Entrée pour l'orchestrateur : run(bridge_module, "local-fast") -> rapport.
Le profil doit déjà avoir été démarré avec le bridge ; aucune construction implicite.
Chaque injection possède son finally de restauration. Un échec arrête la campagne.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import bridge_runtime as rt


UNIT = 10**18
CASES = (
    "historical_restart", "duplicate_recollection", "pause_resume", "destination_rpc_timeout",
    "insufficient_gas", "concurrent_processes", "crash_after_signed_persisted",
    "crash_after_broadcast", "reorg_before_finality",
)
EXPECTED = {
    "historical_restart": "Burn pendant l'arrêt du relayer, collecte historique à la reprise, un seul mint et checkpoint avancé.",
    "duplicate_recollection": "Relecture d'un bloc déjà traité : une observation canonique, une ligne de transfert, même nonce/hash et aucun mint supplémentaire.",
    "pause_resume": "Pause par le rôle distinct : attente persistante sans nonce réservé ; reprise par l'administrateur puis un mint.",
    "destination_rpc_timeout": "RPC destination suspendu : cycle explicitement dégradé, collecte bloquée ; restauration, collecte historique puis un mint.",
    "insufficient_gas": "Gas du signataire à zéro : waiting_gas sans nonce réservé ; rechargement local puis un mint.",
    "concurrent_processes": "Deux processus relayer actifs : plusieurs transferts distincts, nonces distincts et un effet par transfert.",
    "crash_after_signed_persisted": "Arrêt réel après signature persistée avant diffusion ; reprise avec le même nonce/hash et un mint.",
    "crash_after_broadcast": "Arrêt réel après retour de diffusion avant écriture submitted ; reprise avec le même nonce/hash et un mint.",
    "reorg_before_finality": "Burn observé avant finalité, branche remplacée : observation non canonique conservée, rejet source_reorg et aucun mint.",
}


class CaseFailure(RuntimeError):
    pass


def source_files(b):
    paths = [Path(__file__), b.ROOT / "scripts/bridge.py", b.ROOT / "scripts/bridge_runtime.py"]
    for folder in ("src", "contracts/src", "contracts/vendor", "sandbox"):
        paths.extend(p for p in (b.ROOT / folder).rglob("*")
                     if p.is_file() and not {"bin", "obj", "__pycache__"}.intersection(p.parts))
    return {p.relative_to(b.ROOT).as_posix(): b.digest(p.read_bytes()) for p in sorted(set(paths))}


class Campaign:
    def __init__(self, b, name):
        self.b, self.name = b, name
        self.profile = b.profile(name, runnable=True)
        self.config = b.read_json(b.runtime(name) / "deployment.json")
        self.chains, self.networks = self.profile["chains"], self.config["networks"]
        self.postgres = b.container_id(name, "postgres")
        self.current = None

    def check(self, name, expected, observed, passed):
        check = {"id": name, "expected": expected, "observed": observed, "passed": bool(passed), "utc": self.b.utc()}
        self.current["checks"].append(check)
        if not passed:
            raise CaseFailure(name + " : " + expected)
        return observed

    def sql(self, sql):
        # Aucun SELECT signed_raw : seuls son existence, les hashes et les nonces sont observés.
        procedures = self.current.setdefault("database_procedures", [])
        if sql not in procedures:
            procedures.append(sql)
        result = self.b.run(["docker", "exec", "-i", self.postgres, "psql", "-X", "-q", "-A", "-t",
                             "-v", "ON_ERROR_STOP=1", "-U", "sandbox_admin", "-d", "bridge"],
                            stdin_text=sql, timeout=30)
        return result["stdout"]

    def row(self, transfer_id):
        if not re.fullmatch(r"0x[0-9a-fA-F]{64}", transfer_id):
            raise ValueError("Identifiant de transfert invalide")
        raw = self.sql("SELECT row_to_json(t) FROM (SELECT id,state,error_code,attempts,source_chain,source_block,"
                       "source_block_hash,destination_nonce,destination_hash,destination_block,"
                       "signed_raw IS NOT NULL AS has_signed_payload FROM bridge.transfers WHERE id='"
                       + transfer_id.lower() + "') t;")
        return json.loads(raw) if raw else None

    def checkpoint(self, index):
        return int(self.sql("SELECT next_block FROM bridge.networks WHERE chain_id="
                            + str(int(self.networks[index]["chainId"])) + ";"))

    def counts(self, transfer_id):
        if not re.fullmatch(r"0x[0-9a-fA-F]{64}", transfer_id):
            raise ValueError("Identifiant de transfert invalide")
        return json.loads(self.sql("SELECT json_build_object('transfers',(SELECT count(*) FROM bridge.transfers WHERE id='"
            + transfer_id.lower() + "'),'observations',(SELECT count(*) FROM bridge.observations WHERE transfer_id='"
            + transfer_id.lower() + "'),'canonical',(SELECT count(*) FROM bridge.observations WHERE transfer_id='"
            + transfer_id.lower() + "' AND canonical));"))

    def wait(self, observe, predicate, label, timeout=90):
        deadline, last, progress = time.monotonic() + timeout, None, time.monotonic() + 25
        while time.monotonic() < deadline:
            last = observe()
            if predicate(last):
                return last
            if time.monotonic() >= progress:
                print(json.dumps({"case": self.current["id"], "waiting": label, "utc": self.b.utc()}), flush=True)
                progress = time.monotonic() + 25
            time.sleep(1)
        self.check(label, "Condition atteinte dans " + str(timeout) + " secondes", last, False)

    def state(self, transfer, states, timeout=90):
        return self.wait(lambda: self.row(transfer["transfer_id"]),
                         lambda row: row is not None and row["state"] in states,
                         "état " + "/".join(states), timeout)

    def running_relayers(self):
        result = self.b.compose(self.name, ["--profile", "bridge", "ps", "--status", "running", "--quiet", "relayer"])
        return result["stdout"].splitlines() if result["stdout"] else []

    def stop(self):
        self.b.compose(self.name, ["--profile", "bridge", "stop", "--timeout", "10", "relayer"], timeout=45)

    def start(self):
        self.b.compose(self.name, ["--profile", "bridge", "start", "relayer"], timeout=45)

    def balance(self, index, account=None):
        n, c = self.networks[index], self.chains[index]
        return int(rt.call(self.b, c, n["tokenAddress"], "balanceOf(address)", [account or n["adminAddress"]]), 16)

    def processed(self, transfer):
        index = next(i for i, n in enumerate(self.networks) if n["chainId"] != transfer["source"])
        return bool(int(rt.call(self.b, self.chains[index], self.networks[index]["bridgeAddress"],
                                "processed(bytes32)", [transfer["transfer_id"]]), 16))

    def transfer(self, amount=UNIT):
        transfer = rt.transfer(self.b, self.name, 0, amount)
        self.current.setdefault("transfers", []).append(transfer)
        return transfer

    def finish(self, transfer, timeout=180):
        receipt = rt.await_mint(self.b, self.name, transfer, timeout=timeout)
        transfer["mint_receipt"] = receipt
        row = self.state(transfer, ["destination_finalized"], timeout=30)
        self.check("mint_unique_" + transfer["transfer_id"], "Un reçu réussi et un transfert finalisé persistant",
                   {"row": row, "receipt_hash": receipt["transactionHash"], "receipt_status": receipt["status"]},
                   int(receipt["status"], 16) == 1 and row["destination_hash"].lower() == receipt["transactionHash"].lower())
        return row

    def quiescent(self):
        count = int(self.sql("SELECT count(*) FROM bridge.transfers WHERE state NOT IN ('destination_finalized','rejected');"))
        return count == 0

    def preflight(self):
        expected_image = rt.image(self.b, "relayer")
        self.check("contract_sources", "Sources des contrats identiques au déploiement", self.config["contractSourcesSha256"],
                   self.config["contractSourcesSha256"] == rt.contract_fingerprint(self.b))
        running = self.running_relayers()
        self.check("one_relayer", "Un processus relayer de référence actif", running, len(running) == 1)
        actual_image = self.b.run(["docker", "inspect", running[0], "--format", "{{.Image}}"]) ["stdout"]
        self.check("running_image", "Image exécutée identique aux sources construites", actual_image, actual_image == expected_image)
        signer = self.b.container_id(self.name, "signer")
        signer_image = self.b.run(["docker", "inspect", signer, "--format", "{{.Image}}"]) ["stdout"]
        self.check("signer_image", "Image du signataire identique aux sources construites", signer_image,
                   signer_image == rt.image(self.b, "signer"))
        self.wait(lambda: rt.read_status(self.b, self.name), lambda s: s["ready"], "relayer prêt", timeout=60)
        self.wait(self.quiescent, bool, "aucun transfert antérieur en cours", timeout=180)
        for c, n in zip(self.chains, self.networks):
            observation = self.b.chain_observation(c)
            self.check("genesis_" + n["name"], "Identité réseau du déploiement conservée", observation,
                       observation["genesis_hash"].lower() == n["genesisHash"].lower())
            paused = int(rt.call(self.b, c, n["bridgeAddress"], "paused()"), 16)
            self.check("unpaused_" + n["name"], "Bridge initialement actif", paused, paused == 0)

    def historical_restart(self):
        before, checkpoint = self.balance(1), self.checkpoint(0)
        try:
            self.stop()
            self.check("stopped", "Aucun processus relayer actif", self.running_relayers(), not self.running_relayers())
            transfer = self.transfer()
            observed = {"row": self.row(transfer["transfer_id"]), "processed": self.processed(transfer)}
            self.check("uncollected", "Burn réussi sans collecte ni mint pendant l'arrêt", observed,
                       observed["row"] is None and not observed["processed"])
        finally:
            self.start()
        self.finish(transfer)
        current = self.checkpoint(0)
        counts = self.counts(transfer["transfer_id"])
        self.check("historical_recovered", "Checkpoint au-delà du burn et un effet métier exact",
                   {"checkpoint_before": checkpoint, "checkpoint_after": current, "counts": counts,
                    "destination_balance": str(self.balance(1))},
                   current > int(transfer["burn_receipt"]["blockNumber"], 16)
                   and counts == {"transfers": 1, "observations": 1, "canonical": 1}
                   and self.balance(1) == before + UNIT)

    def duplicate_recollection(self):
        transfer = self.transfer()
        original = self.finish(transfer)
        before, counts, checkpoint = self.balance(1), self.counts(transfer["transfer_id"]), self.checkpoint(0)
        try:
            self.stop()
            height = int(transfer["burn_receipt"]["blockNumber"], 16)
            self.sql("UPDATE bridge.networks SET next_block=" + str(height) + " WHERE chain_id="
                     + str(self.networks[0]["chainId"]) + ";")
            self.check("rewound_checkpoint", "Relecture explicitement déclenchée au bloc du burn", self.checkpoint(0),
                       self.checkpoint(0) == height)
        finally:
            self.start()
        self.wait(lambda: self.checkpoint(0), lambda n: n >= checkpoint, "recollecte terminée")
        final = self.finish(transfer)
        after = self.counts(transfer["transfer_id"])
        self.check("duplicate_no_effect", "Ni ligne, ni nonce, ni mint supplémentaire",
                   {"before": counts, "after": after, "row": final, "destination_balance": str(self.balance(1))},
                   counts == after == {"transfers": 1, "observations": 1, "canonical": 1}
                   and final["destination_nonce"] == original["destination_nonce"]
                   and final["destination_hash"] == original["destination_hash"] and self.balance(1) == before)

    def set_pause(self, index, paused):
        c, n = self.chains[index], self.networks[index]
        sender = n["pauserAddress"] if paused else n["adminAddress"]
        key = None if c["client_prefix"] == "anvil" else self.b.runtime(self.name) / ("pauser_key" if paused else "operator_key")
        return rt.transaction(self.b, self.name, c, sender, n["bridgeAddress"],
                              rt.calldata(self.b, c, "pause()" if paused else "unpause()"), key_file=key)

    def pause_resume(self):
        n = self.networks[1]
        self.check("distinct_roles", "Pauser distinct de l'administrateur et de l'exécuteur",
                   {k: n[k] for k in ("pauserAddress", "adminAddress", "signerAddress")},
                   len({n[k].lower() for k in ("pauserAddress", "adminAddress", "signerAddress")}) == 3)
        before = self.balance(1)
        try:
            self.current["pause_receipt"] = self.set_pause(1, True)
            transfer = self.transfer()
            row = self.state(transfer, ["waiting_pause"])
            self.check("paused_wait", "Aucun effet, nonce ou signature pendant la pause", row,
                       not self.processed(transfer) and self.balance(1) == before
                       and row["destination_nonce"] is None and not row["has_signed_payload"])
        finally:
            if int(rt.call(self.b, self.chains[1], n["bridgeAddress"], "paused()"), 16):
                self.current["unpause_receipt"] = self.set_pause(1, False)
        self.finish(transfer)
        self.check("resumed_amount", "Montant exact créé après levée administrative", str(self.balance(1)), self.balance(1) == before + UNIT)

    def destination_rpc_timeout(self):
        cid = self.b.container_id(self.name, self.chains[1]["service"])
        before = self.balance(1)
        try:
            self.b.run(["docker", "pause", cid])
            paused = self.b.run(["docker", "inspect", cid, "--format", "{{.State.Paused}}"]) ["stdout"]
            self.check("rpc_paused", "Processus destination réellement suspendu", paused, paused == "true")
            degraded = self.wait(lambda: rt.read_status(self.b, self.name),
                                 lambda s: not s["ready"] and str(s.get("errorCode") or "").startswith("rpc_"),
                                 "cycle arrêté sur échec RPC", timeout=45)
            checkpoint = self.checkpoint(0)
            transfer = self.transfer()
            # Les deux identités sont vérifiées avant toute collecte : le burn reste historique.
            row = self.row(transfer["transfer_id"])
            self.check("global_identity_gate", "Échec RPC explicite ; checkpoint conservé, burn non encore collecté",
                       {"error_code": degraded["errorCode"], "updated_utc": degraded["updatedUtc"],
                        "checkpoint_before": checkpoint, "checkpoint_after": self.checkpoint(0), "row": row},
                       row is None and self.checkpoint(0) == checkpoint)
        finally:
            paused = self.b.run(["docker", "inspect", cid, "--format", "{{.State.Paused}}"]) ["stdout"]
            if paused == "true":
                self.b.run(["docker", "unpause", cid])
        self.finish(transfer)
        self.check("rpc_recovery_amount", "Un seul montant après restauration du RPC", str(self.balance(1)), self.balance(1) == before + UNIT)

    def insufficient_gas(self):
        c, n = self.chains[1], self.networks[1]
        previous = self.b.rpc(c["rpc_host"], "eth_getBalance", [n["signerAddress"], "latest"])
        before = self.balance(1)
        try:
            self.b.rpc(c["rpc_host"], "anvil_setBalance", [n["signerAddress"], "0x0"])
            gas = self.b.rpc(c["rpc_host"], "eth_getBalance", [n["signerAddress"], "latest"])
            self.check("empty_gas", "Solde gas de test nul", gas, int(gas, 16) == 0)
            transfer = self.transfer()
            row = self.state(transfer, ["waiting_gas"])
            self.check("gas_wait", "Aucun mint, nonce réservé ou signature sans gas", row,
                       not self.processed(transfer) and self.balance(1) == before
                       and row["destination_nonce"] is None and not row["has_signed_payload"])
        finally:
            self.b.rpc(c["rpc_host"], "anvil_setBalance", [n["signerAddress"], previous])
        self.finish(transfer)
        self.check("gas_recovery_amount", "Un seul montant après financement local", str(self.balance(1)), self.balance(1) == before + UNIT)

    def concurrent_processes(self):
        before, transfers = self.balance(1), []
        try:
            self.b.compose(self.name, ["--profile", "bridge", "up", "--detach", "--pull", "never", "--no-deps",
                                        "--scale", "relayer=2", "relayer"], timeout=90)
            running = self.wait(self.running_relayers, lambda ids: len(ids) == 2, "deux processus actifs", timeout=30)
            self.check("two_processes", "Deux conteneurs relayer distincts actifs", running, len(set(running)) == 2)
            transfers = [self.transfer(UNIT), self.transfer(2 * UNIT)]
            rows = [self.finish(t) for t in transfers]
            nonces = [r["destination_nonce"] for r in rows]
            still_running = self.running_relayers()
            self.check("concurrent_unique", "Nonces distincts, un effet par transfert et somme exacte",
                       {"nonces": nonces, "rows": rows, "processes_after": still_running, "destination_balance": str(self.balance(1))},
                       None not in nonces and len(set(nonces)) == 2 and self.balance(1) == before + 3 * UNIT
                       and set(still_running) == set(running)
                       and all(self.counts(t["transfer_id"]) == {"transfers": 1, "observations": 1, "canonical": 1} for t in transfers))
        finally:
            self.b.compose(self.name, ["--profile", "bridge", "up", "--detach", "--pull", "never", "--no-deps",
                                        "--scale", "relayer=1", "relayer"], timeout=90)
            restored = self.running_relayers()
            self.check("process_count_restored", "Retour à un processus relayer", restored, len(restored) == 1)

    def crash(self, point):
        container = self.b.project(self.name) + "-fault-" + uuid.uuid4().hex[:12]
        expected_exit = 91 if point == "after_signed_persisted" else 92
        before = self.balance(1)
        try:
            self.stop()
            transfer = self.transfer()
            self.b.compose(self.name, ["--profile", "bridge", "run", "--detach", "--pull", "never", "--no-deps", "--name", container,
                       "--env", "BRIDGE_FAULT_POINT=" + point, "--env", "BRIDGE_FAULT_TRANSFER_ID=" + transfer["transfer_id"],
                       "relayer"], timeout=60)
            def process_state():
                return json.loads(self.b.run(["docker", "inspect", container, "--format", "{{json .State}}"])["stdout"])
            state = self.wait(process_state, lambda s: not s["Running"], "arrêt réel au point de faute", timeout=150)
            row = self.row(transfer["transfer_id"])
            self.check("process_exit", "Code de sortie exact du point de crash", state, state["ExitCode"] == expected_exit)
            self.check("durable_signature", "Signature et nonce persistés, état prepared", row,
                       row["state"] == "destination_prepared" and row["has_signed_payload"]
                       and row["destination_nonce"] is not None and row["destination_hash"] is not None)
            known = self.b.rpc(self.chains[1]["rpc_host"], "eth_getTransactionByHash", [row["destination_hash"]])
            if point == "after_signed_persisted":
                self.check("not_broadcast", "Transaction inconnue destination avant diffusion", {"transaction_known": known is not None, "attempts": row["attempts"]},
                           known is None and row["attempts"] == 0 and not self.processed(transfer))
            else:
                self.check("broadcast_before_crash", "Transaction connue malgré état local prepared",
                           {"transaction_hash": known.get("hash") if known else None, "attempts": row["attempts"]},
                           known is not None and known["hash"].lower() == row["destination_hash"].lower() and row["attempts"] >= 1)
                self.current["limit"] = "Crash après réponse RPC positive avant persistance ; une réponse RPC perdue n'est pas injectée ici."
        finally:
            try:
                # Une erreur de Compose peut survenir après la création : chercher ce nom unique même dans ce cas.
                inspection = self.b.run(["docker", "inspect", container, "--format", '{{index .Config.Labels "com.docker.compose.project"}}'], check=False)
                if inspection["exit_code"] == 0:
                    label = inspection["stdout"]
                    if label != self.b.project(self.name):
                        raise CaseFailure("Ressource de faute hors projet ; nettoyage refusé")
                    self.b.run(["docker", "rm", "--force", container])
            finally:
                self.start()
        final = self.finish(transfer)
        self.check("same_transaction", "Même nonce et hash signés après reprise, effet unique",
                   {"before": row, "after": final, "destination_balance": str(self.balance(1))},
                   final["destination_nonce"] == row["destination_nonce"]
                   and final["destination_hash"] == row["destination_hash"] and self.balance(1) == before + UNIT)

    def crash_after_signed_persisted(self):
        self.crash("after_signed_persisted")

    def crash_after_broadcast(self):
        self.crash("after_broadcast")

    def reorg_before_finality(self):
        c, n = self.chains[0], self.networks[0]
        auto = self.b.rpc(c["rpc_host"], "anvil_getAutomine")
        interval_raw = self.b.rpc(c["rpc_host"], "anvil_getIntervalMining")
        interval = int(interval_raw, 16) if isinstance(interval_raw, str) else int(interval_raw or 0)
        before, source_before = self.balance(1), self.balance(0)
        self.current["mining_before"] = {"automine": auto, "interval_seconds": interval}
        self.current["method_reference"] = "https://foundry-rs.github.io/foundry/anvil/eth/api/struct.EthApi.html"
        try:
            self.b.rpc(c["rpc_host"], "evm_setIntervalMining", [0])
            self.b.rpc(c["rpc_host"], "evm_setAutomine", [True])
            head = int(self.b.rpc(c["rpc_host"], "eth_blockNumber"), 16)
            self.wait(lambda: self.checkpoint(0), lambda p: p > head, "checkpoint avant snapshot")
            snapshot = self.b.rpc(c["rpc_host"], "evm_snapshot")
            # Montant propre au scénario : une campagne suivante peut réutiliser le nonce restauré
            # pour un transfert normal sans confondre son ID avec celui de ce burn orphelin.
            transfer = self.transfer(3 * UNIT)
            old = self.state(transfer, ["waiting_finality"])
            before_counts = self.counts(transfer["transfer_id"])
            self.check("observed_unfinalized", "Burn observé sans nonce destination avant finalité", old,
                       old["destination_nonce"] is None and not self.processed(transfer)
                       and old["source_block_hash"] == transfer["burn_receipt"]["blockHash"]
                       and before_counts["canonical"] == 1)
            reverted = self.b.rpc(c["rpc_host"], "evm_revert", [snapshot])
            self.check("branch_reverted", "Snapshot réellement restauré", reverted, reverted is True)
            burn_height = int(transfer["burn_receipt"]["blockNumber"], 16)
            # Plusieurs blocs vides remplacent les transactions de l'ancienne branche.
            for _ in range(burn_height - head + self.chains[0]["finality"]["depth"] + 1):
                self.b.rpc(c["rpc_host"], "evm_mine")
            alternate = self.b.rpc(c["rpc_host"], "eth_getBlockByNumber", [hex(burn_height), False])
            receipt = self.b.rpc(c["rpc_host"], "eth_getTransactionReceipt", [transfer["burn_receipt"]["transactionHash"]])
            row = self.state(transfer, ["rejected", "intervention_required"])
            counts = self.counts(transfer["transfer_id"])
            self.check("orphan_preserved", "Ancien burn disparu, observation conservée non canonique et rejet explicite",
                       {"old_hash": transfer["burn_receipt"]["blockHash"], "new_hash": alternate["hash"],
                        "old_receipt": receipt, "row": row, "counts": counts},
                       alternate["hash"] != transfer["burn_receipt"]["blockHash"] and receipt is None
                       and row["state"] == "rejected" and row["error_code"] == "source_reorg"
                       and counts == {"transfers": 1, "observations": before_counts["observations"], "canonical": 0})
            self.check("no_orphan_mint", "Aucun mint pour la branche supprimée et balance source restaurée",
                       {"processed": self.processed(transfer), "source_balance": str(self.balance(0)),
                        "destination_balance": str(self.balance(1))},
                       not self.processed(transfer) and self.balance(0) == source_before and self.balance(1) == before)
            self.current["limit"] = "Scénario Anvil préfinalité uniquement ; ne démontre aucune finalité TELA."
        finally:
            try:
                self.b.rpc(c["rpc_host"], "evm_setAutomine", [auto])
            finally:
                self.b.rpc(c["rpc_host"], "evm_setIntervalMining", [interval])
            restored_auto = self.b.rpc(c["rpc_host"], "anvil_getAutomine")
            restored_interval = self.b.rpc(c["rpc_host"], "anvil_getIntervalMining")
            restored_interval = int(restored_interval, 16) if isinstance(restored_interval, str) else int(restored_interval or 0)
            self.check("mining_restored", "Mode de minage initial restauré",
                       {"automine": restored_auto, "interval_seconds": restored_interval},
                       restored_auto == auto and restored_interval == interval)


def run(b, name, cases=None):
    """Exécute les injections sélectionnées sur une sandbox déjà active et sauvegarde le rapport."""
    b.profile(name, runnable=True)
    selected = list(CASES if cases is None else cases)
    if not selected or any(case not in CASES for case in selected) or len(set(selected)) != len(selected):
        raise ValueError("Sélection de scénarios invalide")
    begin = len(b.RECORDS)
    before_sources = source_files(b)
    report = {"schema_version": 1, "startedUtc": b.utc(), "profile": name, "scope": "Campagne locale historique, pas un tableau en direct",
              "source_commit": b.run(["git", "rev-parse", "HEAD"])["stdout"],
              "git_status": b.run(["git", "status", "--porcelain=v1"])["stdout"],
              "source_files": before_sources, "source_sha256": b.digest(b.canonical(before_sources)), "passed": False, "cases": [],
              "external_emissions": "Aucune émission externe ni autre producteur de transfert autorisé pendant cette campagne."}
    output = b.LOCAL / (name + "-resilience.json")
    archive = b.LOCAL / "resilience" / (name + "-" + report["startedUtc"].replace(":", "").replace("-", "")
                                       + "-" + uuid.uuid4().hex[:8] + ".json")
    report["archive"] = archive.relative_to(b.ROOT).as_posix()
    # Empêche deux campagnes de faute simultanées ; ne remplace pas une réservation humaine de l'hôte.
    lock = b.runtime(name) / "resilience.lock"
    with lock.open("x", encoding="utf-8") as stream:
        stream.write(b.utc() + "\n")
    try:
        h = Campaign(b, name)
        report["deployment"] = {"deployedUtc": h.config["deployedUtc"], "networks": h.networks,
                                "referenceSupply": h.config["referenceSupply"]}
        report["build"] = b.read_json(b.LOCAL / "build.json")
        report["images_locked"] = b.lock()["images"]
        preflight = {"id": "preflight", "startedUtc": b.utc(), "checks": [], "status": "running"}
        report["cases"].append(preflight)
        h.current = preflight
        h.preflight()
        preflight.update(status="passed", endedUtc=b.utc())
        failed = False
        for case in selected:
            result = {"id": case, "expected": EXPECTED[case], "startedUtc": b.utc(), "checks": []}
            report["cases"].append(result)
            if failed:
                result.update(status="not_executed", reason="Campagne interrompue après échec pour éviter les effets en cascade.")
                continue
            if name != "local-fast" and case in ("insufficient_gas", "reorg_before_finality"):
                result.update(status="not_executed", reason="Injection Anvil réservée au profil local-fast ; aucune validation Besu de ce scénario.")
                continue
            h.current = result
            print(json.dumps({"resilience_case": case, "profile": name, "utc": b.utc()}, ensure_ascii=False), flush=True)
            try:
                getattr(h, case)()
                h.wait(h.quiescent, bool, "état terminal après scénario", timeout=180)
                result["status"] = "passed"
            except Exception as exc:
                result.update(status="failed", error=type(exc).__name__ + ": " + str(exc))
                failed = True
            result["endedUtc"] = b.utc()
            b.write_json(archive, report)
            b.write_json(output, report)
        report["passed"] = not failed and all(c["status"] in ("passed", "not_executed") for c in report["cases"])
        report["executed_passed"] = sum(c["status"] == "passed" for c in report["cases"] if c["id"] != "preflight")
        report["not_executed"] = [c["id"] for c in report["cases"] if c["status"] == "not_executed"]
        report["passed"] = report["passed"] and report["executed_passed"] > 0
    except Exception as exc:
        report["error"] = type(exc).__name__ + ": " + str(exc)
        for case in report["cases"]:
            if case.get("status") == "running":
                case.update(status="failed", endedUtc=b.utc())
    finally:
        report["endedUtc"] = b.utc()
        after_sources = source_files(b)
        report["source_files_after"] = after_sources
        report["source_sha256_after"] = b.digest(b.canonical(after_sources))
        report["changed_source_files"] = [p for p in sorted(set(before_sources) | set(after_sources))
                                          if before_sources.get(p) != after_sources.get(p)]
        report["sources_unchanged"] = report["source_sha256"] == report["source_sha256_after"]
        report["passed"] = report["passed"] and report["sources_unchanged"]
        report["commands"] = b.RECORDS[begin:]
        b.write_json(archive, report)
        b.write_json(output, report)
        lock.unlink()
    print(json.dumps({"resilience_passed": report["passed"], "report": str(output), "utc": b.utc()}), flush=True)
    return report


if __name__ == "__main__":
    import bridge
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("local-fast", "local-besu"), default="local-fast")
    parser.add_argument("--case", action="append", choices=CASES, dest="cases")
    arguments = parser.parse_args()
    try:
        result = run(bridge, arguments.profile, arguments.cases)
        raise SystemExit(0 if result["passed"] else 1)
    except (bridge.BridgeError, FileExistsError, ValueError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
