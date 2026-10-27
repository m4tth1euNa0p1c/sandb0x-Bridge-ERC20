"""Build, déploiement et expériences locales. Aucune connexion à un testnet partagé."""
from __future__ import annotations

import json
import os
from pathlib import Path
import secrets
import tempfile
import time
import urllib.request


def build_fingerprint(b):
    paths = [b.ROOT / "global.json", b.ROOT / "NuGet.config", b.ROOT / "sandbox/versions.lock.json",
             b.ROOT / "sandbox/Dockerfile.dotnet", b.ROOT / "sandbox/Dockerfile.besu", b.ROOT / "sandbox/Dockerfile.tests",
             b.ROOT / "sandbox/besu-healthcheck.sh"]
    paths += [p for p in (b.ROOT / "src").rglob("*") if p.is_file() and not {"obj", "bin"}.intersection(p.parts)]
    return b.digest(b.canonical({p.relative_to(b.ROOT).as_posix(): b.digest(p.read_bytes()) for p in sorted(paths)}))


def test_fingerprint(b):
    paths = [p for p in (b.ROOT / "tests").glob("Bridge.*.Tests/**/*") if p.is_file() and not {"obj", "bin", "TestResults"}.intersection(p.parts)]
    paths += list((b.ROOT / "contracts/vectors").glob("*.json"))
    return b.digest(b.canonical({p.relative_to(b.ROOT).as_posix(): b.digest(p.read_bytes()) for p in sorted(paths)}))


def build(b, include_tests=True):
    """Phase installation : NuGet et images. Aucun secret dans le contexte Docker."""
    report = {"utc": b.utc(), "source_sha256": build_fingerprint(b), "test_sha256": test_fingerprint(b), "images": {}}
    for component in ("Signer", "Relayer", "Operator"):
        print("Construction .NET : " + component, flush=True)
        tag = "t3l4n-bridge-" + component.lower() + ":" + report["source_sha256"][:16]
        b.run(["docker", "build", "--platform", "linux/amd64", "--pull=false", "-f", "sandbox/Dockerfile.dotnet",
               "--build-arg", "SDK_IMAGE=" + b.lock()["images"]["dotnet_sdk"],
               "--build-arg", "RUNTIME_IMAGE=" + b.lock()["images"]["dotnet_runtime"],
               "--build-arg", "COMPONENT=" + component, "-t", tag, "."], timeout=600)
        report["images"][component.lower()] = b.run(["docker", "image", "inspect", tag, "--format", "{{.Id}}"])["stdout"]
        if component != "Operator" and include_tests:
            tag = "t3l4n-bridge-test-" + component.lower() + ":" + report["source_sha256"][:16]
            b.run(["docker", "build", "--platform", "linux/amd64", "--pull=false", "-f", "sandbox/Dockerfile.tests",
                   "--build-arg", "SDK_IMAGE=" + b.lock()["images"]["dotnet_sdk"],
                   "--build-arg", "COMPONENT=" + component, "-t", tag, "."], timeout=600)
            report["images"]["test_" + component.lower()] = b.run(["docker", "image", "inspect", tag, "--format", "{{.Id}}"])["stdout"]
    tag = "t3l4n-bridge-besu:" + report["source_sha256"][:16]
    b.run(["docker", "build", "--platform", "linux/amd64", "--pull=false", "-f", "sandbox/Dockerfile.besu",
           "--build-arg", "BESU_IMAGE=" + b.lock()["images"]["besu"], "-t", tag, "."], timeout=120)
    report["images"]["besu_node"] = b.run(["docker", "image", "inspect", tag, "--format", "{{.Id}}"])["stdout"]
    if report["source_sha256"] != build_fingerprint(b):
        raise b.BridgeError("Sources modifiées pendant le build ; relancer build")
    if include_tests and report["test_sha256"] != test_fingerprint(b):
        raise b.BridgeError("Tests modifiés pendant le build ; relancer build")
    b.write_json(b.LOCAL / "build.json", report)
    return report


def image(b, component):
    path = b.LOCAL / "build.json"
    if not path.is_file():
        raise b.BridgeError("Images applicatives absentes : lancer build pendant la phase installation")
    manifest = b.read_json(path)
    if manifest["source_sha256"] != build_fingerprint(b):
        raise b.BridgeError("Images applicatives obsolètes : relancer build")
    if component.startswith("test_") and manifest.get("test_sha256") != test_fingerprint(b):
        raise b.BridgeError("Images de test obsolètes : relancer build")
    if component not in manifest["images"]:
        raise b.BridgeError("Image absente : relancer build complet")
    return manifest["images"][component]


def tests(b):
    import xml.etree.ElementTree as ET
    report = {"utc": b.utc(), "components": {}}
    for component in ("Signer", "Relayer"):
        out = b.LOCAL / "test-results" / component.lower()
        out.mkdir(parents=True, exist_ok=True)
        out.chmod(0o777)
        # Les images contiennent déjà dépendances et binaires : tests sans réseau.
        result = b.run(["docker", "run", "--rm", "--pull", "never", "--network", "none", "--user", "1654:1654",
                       "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
                       "--memory", "768m", "--cpus", "2", "--pids-limit", "256",
                       "--tmpfs", "/tmp:rw,nosuid,size=128m",
                       "--tmpfs", "/run/dotnet:rw,noexec,nosuid,size=16m,uid=1654,gid=1654,mode=0700",
                       "-e", "XDG_RUNTIME_DIR=/run/dotnet", "-v", str(out) + ":/results",
                       image(b, "test_" + component.lower()), "dotnet", "test",
                       "tests/Bridge." + component + ".Tests/Bridge." + component + ".Tests.csproj",
                       "-c", "Release", "--no-build", "--no-restore", "--logger", "trx;LogFileName=results.trx",
                       "--results-directory", "/results"], timeout=240)
        tree = ET.parse(out / "results.trx")
        counters = tree.find(".//{http://microsoft.com/schemas/VisualStudio/TeamTest/2010}Counters")
        if counters is None or int(counters.attrib["total"]) == 0 or counters.attrib["total"] != counters.attrib["passed"]:
            raise b.BridgeError("Un test .NET a échoué ou n'a pas été exécuté")
        report["components"][component] = {"counters": counters.attrib, "command": result,
                                           "trx_sha256": b.digest((out / "results.trx").read_bytes())}
    b.write_json(b.LOCAL / "dotnet-tests.json", report)
    return report


def docker_run(b, name, component, mounts, args):
    uid = "1654:1654" if os.name == "nt" or os.getuid() == 0 else f"{os.getuid()}:{os.getgid()}"
    return b.run(["docker", "run", "--rm", "--pull", "never", "--network", "none",
                  "--label", "com.t3l4n.project=" + b.project(name), "--user", uid, "--read-only",
                  "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true", "--memory", "256m",
                  "--cpus", "1", "--pids-limit", "128", "--tmpfs", "/tmp:rw,nosuid,noexec,size=32m",
                  *sum((["-v", str(src) + ":" + target] for src, target in mounts), []),
                  image(b, component), "dotnet", "Bridge." + component.title() + ".dll", *args], timeout=60)


def prepare(b, name):
    b.profile(name, runnable=True)
    image(b, "signer")
    target = b.runtime(name)
    target.mkdir(parents=True, exist_ok=True)
    target.chmod(0o700)
    addresses_file = target / "key-addresses.json"
    addresses = b.read_json(addresses_file) if addresses_file.exists() else {}
    for key in ("key_a", "key_b", "operator_key", "pauser_key"):
        path = target / key
        if not path.exists():
            # Le signataire voit seulement ce répertoire temporaire vide, pas les autres clés.
            with tempfile.TemporaryDirectory(prefix="t3l4n-keygen-", dir=target) as temp:
                Path(temp).chmod(0o777 if os.name == "nt" or os.getuid() == 0 else 0o700)
                result = docker_run(b, name, "signer", [(temp, "/output")], ["--generate-key", "/output/key"])
                generated = Path(temp) / "key"
                if not generated.is_file():
                    raise b.BridgeError("La génération n'a pas produit de fichier clé")
                generated.replace(path)
                path.chmod(0o444)
                address = result["stdout"].strip().splitlines()[-1]
                if not b.re.fullmatch("0x[0-9a-fA-F]{40}", address):
                    raise b.BridgeError("Adresse générée invalide")
                addresses[key] = address
                b.write_json(addresses_file, addresses)
        elif key not in addresses:
            raise b.BridgeError("Clé existante sans adresse de contrôle ; intervention nécessaire")
    for key in ("signer_token", "bridge_db_password", "grafana_password"):
        path = target / key
        if not path.exists():
            path.write_text(secrets.token_hex(32), encoding="ascii")
            path.chmod(0o444)
    if name == "local-besu" and not (target / "genesis.bridge.json").exists():
        genesis = b.read_json(target / "genesis.json")
        genesis.setdefault("alloc", {})[addresses["operator_key"][2:]] = {"balance": hex(10000 * 10**18)}
        # Nouveau volume dédié v2 : aucune suppression de la simulation J1.
        b.write_json(target / "genesis.bridge.json", genesis)
    return addresses


def encode(types, values):
    if len(types) != len(values):
        raise ValueError("ABI argument count")
    heads, tails = [], b""
    for type_, value in zip(types, values):
        if type_ == "string":
            raw = value.encode("utf-8")
            heads.append((32 * len(types) + len(tails)).to_bytes(32, "big"))
            tails += len(raw).to_bytes(32, "big") + raw + b"\0" * ((-len(raw)) % 32)
        elif type_ == "address":
            raw = bytes.fromhex(value.removeprefix("0x"))
            if len(raw) != 20:
                raise ValueError("Invalid ABI address")
            heads.append(raw.rjust(32, b"\0"))
        elif type_ == "bytes32":
            raw = bytes.fromhex(value.removeprefix("0x"))
            if len(raw) != 32:
                raise ValueError("Invalid bytes32")
            heads.append(raw)
        elif type_.startswith("uint"):
            number = int(value)
            bits = int(type_[4:] or 256)
            if number < 0 or number >= 2**bits:
                raise ValueError("Integer out of ABI bounds")
            heads.append(number.to_bytes(32, "big"))
        else:
            raise ValueError("ABI type unsupported")
    return (b"".join(heads) + tails).hex()


def keccak(b, c, raw_hex):
    return b.rpc(c["rpc_host"], "web3_sha3", ["0x" + raw_hex.removeprefix("0x")])


def calldata(b, c, signature, values=()):
    types = signature.split("(", 1)[1].rstrip(")").split(",")
    return keccak(b, c, signature.encode().hex())[:10] + encode(types if types != [""] else [], values)


def call(b, c, to, signature, values=(), block="latest"):
    return b.rpc(c["rpc_host"], "eth_call", [{"to": to, "data": calldata(b, c, signature, values)}, block])


def receipt(b, c, tx_hash, timeout=90):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = b.rpc(c["rpc_host"], "eth_getTransactionReceipt", [tx_hash])
        if result:
            if int(result["status"], 16) != 1:
                raise b.BridgeError("Transaction locale reverted : " + tx_hash)
            return result
        time.sleep(0.5)
    raise b.BridgeError("Reçu non obtenu dans le délai ; résultat ambigu à réconcilier : " + tx_hash)


def confirm_local_receipt(b, name, c, original):
    """Avance bornée du témoin Anvil ; aucune finalité de réseau partagé.

    Un reçu réussi et canonique doit déjà exister. Le relayer n'appelle pas ce
    helper : seuls les scripts du laboratoire produisent les confirmations.
    Une activité concurrente peut ajouter des blocs, jamais augmenter notre
    budget d'au plus `depth` appels de minage.
    """
    p = b.profile(name, runnable=True)
    if c not in p["chains"]:
        raise b.BridgeError("Chaîne hors du profil local : confirmation refusée")
    deployment = b.read_json(b.runtime(name) / "deployment.json")
    networks = [n for n in deployment["networks"] if n["chainId"] == c["chain_id"]]
    if deployment.get("profile") != name or len(networks) != 1:
        raise b.BridgeError("Domaine du déploiement ambigu : confirmation refusée")
    expected = networks[0]
    if original.get("chainId", c["chain_id"]) != c["chain_id"]:
        raise b.BridgeError("Reçu associé à une autre chaîne : confirmation refusée")
    try:
        height = int(original["blockNumber"], 16)
        successful = int(original["status"], 16) == 1
        tx_hash, block_hash = original["transactionHash"], original["blockHash"]
    except (KeyError, TypeError, ValueError) as error:
        raise b.BridgeError("Reçu incomplet : confirmation refusée") from error
    if not successful or height < 0 or not all(isinstance(h, str) and b.re.fullmatch(r"0x[0-9a-fA-F]{64}", h)
                                             for h in (tx_hash, block_hash)):
        raise b.BridgeError("Reçu invalide ou reverted : confirmation refusée")

    def canonical():
        observation = b.chain_observation(c)
        if observation["genesis_hash"].lower() != expected["genesisHash"].lower():
            raise b.BridgeError("Genesis modifié : confirmation refusée")
        actual = b.rpc(c["rpc_host"], "eth_getTransactionReceipt", [tx_hash])
        block = b.rpc(c["rpc_host"], "eth_getBlockByNumber", [hex(height), False])
        if (not actual or not block or actual.get("status") != "0x1"
                or actual.get("transactionHash", "").lower() != tx_hash.lower()
                or actual.get("blockHash", "").lower() != block_hash.lower()
                or actual.get("blockNumber") != original["blockNumber"]
                or block.get("hash", "").lower() != block_hash.lower()
                or block.get("number") != original["blockNumber"]):
            raise b.BridgeError("Reçu absent, remplacé ou non canonique : confirmation refusée")
        if observation["head"] < height:
            raise b.BridgeError("Tête antérieure au reçu : confirmation refusée")
        return observation["head"]

    mode = c["finality"]["mode"]
    depth = c["finality"]["depth"] if mode == "confirmations" else 0
    target = height + depth
    head_before = head = canonical()
    mined = 0
    # Le validateur de profil lie confirmations à Anvil et QBFT au Besu local.
    for _ in range(depth):
        if head >= target:
            break
        b.rpc(c["rpc_host"], "evm_mine")
        mined += 1
        previous = head
        head = canonical()
        if head <= previous:
            raise b.BridgeError("Le minage local n'a pas avancé : arrêt du budget")
    head = canonical()
    if head < target:
        raise b.BridgeError("Profondeur locale non atteinte dans le budget de blocs")
    return {"utc": b.utc(), "chain_id": c["chain_id"], "mode": mode,
            "transaction_hash": tx_hash, "block_hash": block_hash, "block_number": height,
            "target": target, "head_before": head_before, "head_after": head, "mined_blocks": mined}


def confirm_deployment(b, name, deployment):
    """Couvre aussi une reprise entre écriture du dossier et confirmations."""
    selected = []
    for c in b.profile(name, runnable=True)["chains"]:
        receipts = [r for r in deployment["receipts"] if r.get("chainId") == c["chain_id"]]
        if not receipts:
            raise b.BridgeError("Aucun reçu de déploiement associé à cette chaîne")
        last = max(receipts, key=lambda r: int(r["blockNumber"], 16))
        selected.append((c, last))
    return [confirm_local_receipt(b, name, c, last) for c, last in selected]


def transaction(b, name, c, sender, to, data="0x", value=0, key_file=None, gas=500000):
    # Revalider avant toute émission, même si un port local a été réaffecté depuis up.
    b.profile(name, runnable=True)
    observation = b.chain_observation(c)
    deployed = b.runtime(name) / "deployment.json"
    if deployed.is_file():
        expected = next(n for n in b.read_json(deployed)["networks"] if n["chainId"] == c["chain_id"])
        if observation["genesis_hash"].lower() != expected["genesisHash"].lower():
            raise b.BridgeError("Identité genesis modifiée avant émission : refus")
    request = {"from": sender, "data": data, "gas": hex(gas), "gasPrice": hex(2 * 10**9), "value": hex(value)}
    if to:
        request["to"] = to
    if key_file:
        # Signature ponctuelle : seulement requête publique et clé concernée sont montées.
        nonce = int(b.rpc(c["rpc_host"], "eth_getTransactionCount", [sender, "pending"]), 16)
        with tempfile.TemporaryDirectory(prefix="t3l4n-operator-", dir=b.runtime(name)) as temp:
            temp = Path(temp)
            temp.chmod(0o777 if os.name == "nt" or os.getuid() == 0 else 0o700)
            b.write_json(temp / "request.json", {"chainId": c["chain_id"], "nonce": str(nonce), "to": to or "",
                         "data": data, "value": str(value), "gasLimit": gas, "gasPriceWei": str(2 * 10**9)})
            docker_run(b, name, "operator", [(temp, "/operation"), (key_file, "/run/key:ro")],
                       ["/operation/request.json", "/run/key", "/operation/raw.txt"])
            raw = (temp / "raw.txt").read_text().strip()
            expected_hash = keccak(b, c, raw)
            tx_hash = b.rpc(c["rpc_host"], "eth_sendRawTransaction", [raw])
            if tx_hash.lower() != expected_hash.lower():
                raise b.BridgeError("Hash de transaction renvoyé incohérent")
    else:
        tx_hash = b.rpc(c["rpc_host"], "eth_sendTransaction", [request])
    result = receipt(b, c, tx_hash)
    result["chainId"] = c["chain_id"]
    return result


def creation_on_chain(b, c, address, bytecode, receipts):
    # La même adresse peut exister sur plusieurs chaînes.
    for original in receipts:
        if (original.get("contractAddress") or "").lower() != address.lower() or original.get("chainId", c["chain_id"]) != c["chain_id"]:
            continue
        tx = b.rpc(c["rpc_host"], "eth_getTransactionByHash", [original["transactionHash"]])
        actual = b.rpc(c["rpc_host"], "eth_getTransactionReceipt", [original["transactionHash"]])
        if (tx and actual and int(actual["status"], 16) == 1 and actual["blockHash"] == original["blockHash"]
                and (actual.get("contractAddress") or "").lower() == address.lower()
                and actual["transactionHash"] == original["transactionHash"]
                and tx["input"].lower().startswith(bytecode.lower())):
            original["chainId"] = c["chain_id"]
            return original
    raise b.BridgeError("Le bytecode de création enregistré ne correspond pas aux sources compilées sur ce réseau")


def deploy(b, name):
    p = b.profile(name, runnable=True)
    verified = validate_contract_artifacts(b)
    path = b.runtime(name) / "deployment.json"
    if path.exists():
        deployment = b.read_json(path)
        for c, n in zip(p["chains"], deployment["networks"]):
            if b.chain_observation(c)["genesis_hash"].lower() != n["genesisHash"].lower():
                raise b.BridgeError("Le déploiement existant désigne un autre genesis")
            for key in ("token", "bridge"):
                actual = b.rpc(c["rpc_host"], "eth_getCode", [n[key + "Address"], "latest"])
                if keccak(b, c, actual).lower() != n[key + "CodeHash"].lower():
                    raise b.BridgeError("Le code du déploiement existant diffère")
                artifact_name = "BridgeToken" if key == "token" else "Bridge"
                bytecode = b.read_json(b.ROOT / f"contracts/out/{artifact_name}.sol/{artifact_name}.json")["bytecode"]["object"]
                creation_on_chain(b, c, n[key + "Address"], bytecode, deployment["receipts"])
        deployment["contractSourcesSha256"] = contract_fingerprint(b)
        deployment["contractArtifacts"] = verified
        b.write_json(path, deployment)
        deployment["localConfirmations"] = confirm_deployment(b, name, deployment)
        b.write_json(path, deployment)
        return deployment
    addresses = b.read_json(b.runtime(name) / "key-addresses.json")
    deployment = {"profile": name, "referenceSupply": str(1000000 * 10**18), "pollMilliseconds": 1000,
                  "rpcTimeoutSeconds": 5, "maxAttempts": 12, "workers": 2, "networks": [], "receipts": [],
                  "deployedUtc": b.utc(), "contractSourcesSha256": contract_fingerprint(b)}
    deployment["contractArtifacts"] = verified
    # En cas d'interruption avant ce fichier final, ne pas répéter silencieusement les déploiements.
    progress = b.runtime(name) / "deployment-in-progress.json"
    if progress.exists():
        raise b.BridgeError("Déploiement interrompu : consulter deployment-in-progress.json avant reprise manuelle")
    b.write_json(progress, deployment)
    for index, c in enumerate(p["chains"]):
        is_anvil = c["client_prefix"] == "anvil"
        accounts = b.rpc(c["rpc_host"], "eth_accounts") if is_anvil else []
        admin = accounts[0] if is_anvil else addresses["operator_key"]
        pauser = accounts[1] if is_anvil else addresses["pauser_key"]
        key_file = None if is_anvil else b.runtime(name) / "operator_key"
        signer = addresses["key_a" if index == 0 else "key_b"]
        token_code = b.read_json(b.ROOT / "contracts/out/BridgeToken.sol/BridgeToken.json")["bytecode"]["object"]
        arguments = encode(["string", "string", "address", "address", "uint256"],
                           ["Bridge Test " + str(c["chain_id"]), "BT" + str(index), admin, admin,
                            int(deployment["referenceSupply"]) if index == 0 else 0])
        token_receipt = transaction(b, name, c, admin, None, token_code + arguments, key_file=key_file, gas=5000000)
        token = token_receipt["contractAddress"]
        deployment["receipts"].append(token_receipt)
        b.write_json(progress, deployment)
        bridge_code = b.read_json(b.ROOT / "contracts/out/Bridge.sol/Bridge.json")["bytecode"]["object"]
        arguments = encode(["address", "address", "address", "address", "uint256", "uint256", "uint256"],
                           [token, admin, pauser, signer, 1000 * 10**18, 100000 * 10**18, 3600])
        bridge_receipt = transaction(b, name, c, admin, None, bridge_code + arguments, key_file=key_file, gas=6000000)
        address = bridge_receipt["contractAddress"]
        deployment["receipts"].append(bridge_receipt)
        role = keccak(b, c, b"BRIDGE_ROLE".hex())
        deployment["receipts"].append(transaction(b, name, c, admin, token,
            calldata(b, c, "grantRole(bytes32,address)", [role, address]), key_file=key_file))
        if is_anvil:
            b.rpc(c["rpc_host"], "anvil_setBalance", [signer, hex(10 * 10**18)])
        else:
            deployment["receipts"].append(transaction(b, name, c, admin, signer, value=10 * 10**18, key_file=key_file))
            deployment["receipts"].append(transaction(b, name, c, admin, pauser, value=10**18, key_file=key_file))
        n = {"name": "a" if index == 0 else "b", "chainId": c["chain_id"],
             "genesisHash": b.chain_observation(c)["genesis_hash"], "clientPrefix": c["client_prefix"],
             "rpcUrl": c["rpc_internal"], "tokenAddress": token, "bridgeAddress": address,
             "tokenCodeHash": keccak(b, c, b.rpc(c["rpc_host"], "eth_getCode", [token, "latest"])),
             "bridgeCodeHash": keccak(b, c, b.rpc(c["rpc_host"], "eth_getCode", [address, "latest"])),
             "signerAddress": signer, "startBlock": int(bridge_receipt["blockNumber"], 16),
             "finalityMode": c["finality"]["mode"], "confirmations": c["finality"].get("depth", 1),
             "maxTransfer": str(1000 * 10**18), "gasLimit": 350000, "maxGasPriceWei": str(100 * 10**9),
             "keyFile": "/run/secrets/" + ("key_a" if index == 0 else "key_b"),
             "adminAddress": admin, "pauserAddress": pauser}
        deployment["networks"].append(n)
        b.write_json(progress, deployment)
    for index, c in enumerate(p["chains"]):
        n, remote = deployment["networks"][index], deployment["networks"][1 - index]
        deployment["receipts"].append(transaction(b, name, c, n["adminAddress"], n["bridgeAddress"],
            calldata(b, c, "configurePair(uint256,address,address,uint8)",
                     [remote["chainId"], remote["bridgeAddress"], remote["tokenAddress"], 18]),
            key_file=None if c["client_prefix"] == "anvil" else b.runtime(name) / "operator_key"))
    b.write_json(path, deployment)
    progress.unlink()
    deployment["localConfirmations"] = confirm_deployment(b, name, deployment)
    b.write_json(path, deployment)
    return deployment


def contract_fingerprint(b):
    paths = [p for folder in ("src", "vendor") for p in (b.ROOT / "contracts" / folder).rglob("*.sol")]
    paths += [b.ROOT / "contracts/foundry.toml", b.ROOT / "contracts/solc.lock.json"]
    return b.digest(b.canonical({p.relative_to(b.ROOT).as_posix(): b.digest(p.read_bytes()) for p in paths}))


def validate_contract_artifacts(b):
    report_path = b.LOCAL / "contracts-verification.json"
    if not report_path.is_file():
        raise b.BridgeError("Compilation vérifiée absente : lancer python contracts/tools/verify.py")
    report = b.read_json(report_path)
    excluded = {".toolchain", ".artifacts", "out", "cache", "__pycache__"}
    current = {p.relative_to(b.ROOT / "contracts").as_posix(): b.digest(p.read_bytes())
               for p in (b.ROOT / "contracts").rglob("*") if p.is_file()
               and not excluded.intersection(p.relative_to(b.ROOT / "contracts").parts)}
    if report.get("passed") is not True or report.get("source_unchanged") is not True or current != report["source_files"]:
        raise b.BridgeError("Sources de contrats différentes de leur vérification ; relancer verify.py")
    artifacts = report.get("artifacts", {})
    for name in ("Bridge", "BridgeToken"):
        path = f"out/{name}.sol/{name}.json"
        if path not in artifacts or b.digest((b.ROOT / "contracts" / path).read_bytes()) != artifacts[path]["sha256"]:
            raise b.BridgeError("Artefact compilé absent ou modifié depuis la vérification")
    return artifacts


def init_database(b, name):
    # Le mot de passe est lu à l'intérieur de PostgreSQL, jamais dans argv ou une sortie.
    sql = """DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='bridge_app') THEN CREATE ROLE bridge_app LOGIN; END IF; END $$;
SELECT format('ALTER ROLE bridge_app PASSWORD %L', pg_read_file('/run/secrets/bridge_db_password')) \\gexec
GRANT CONNECT ON DATABASE bridge TO bridge_app;
CREATE SCHEMA IF NOT EXISTS bridge AUTHORIZATION bridge_app;
GRANT USAGE, CREATE ON SCHEMA bridge TO bridge_app;
"""
    result = b.run(["docker", "exec", "-i", b.container_id(name, "postgres"), "psql", "-X", "-q",
                    "-v", "ON_ERROR_STOP=1", "-U", "sandbox_admin", "-d", "bridge"], stdin_text=sql)
    return {"exit_code": result["exit_code"], "role": "bridge_app", "schema": "bridge"}


def read_status(b, name):
    p = b.profile(name, runnable=True)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open("http://127.0.0.1:" + str(p["status_port"]) + "/status", timeout=8) as response:
        return json.load(response)


def full_up(b, name):
    prepare(b, name)
    b.up(name)
    deployment = deploy(b, name)
    if deployment["contractSourcesSha256"] != contract_fingerprint(b):
        raise b.BridgeError("Contrats déployés obsolètes ; nouveau déploiement explicite nécessaire")
    init_database(b, name)
    b.compose(name, ["--profile", "bridge", "up", "--detach", "--pull", "never", "--force-recreate",
                     "--no-deps", "signer", "relayer", "bridge-gateway", "prometheus", "grafana",
                     "prometheus-gateway", "grafana-gateway"], timeout=120)
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            status = read_status(b, name)
            if status.get("ready") is True and status.get("stale") is False:
                print(json.dumps({"bridge_started": True, "profile": name, "status": status}, ensure_ascii=False))
                return status
        except Exception:
            pass
        time.sleep(1)
    raise b.BridgeError("Relayer non prêt après démarrage ; consulter status et les logs structurés")


def transfer(b, name, source_index, amount, recipient=None, *, confirm_source=True):
    deployment = b.read_json(b.runtime(name) / "deployment.json")
    c = b.profile(name)["chains"][source_index]
    n, destination = deployment["networks"][source_index], deployment["networks"][1 - source_index]
    recipient = recipient or destination["adminAddress"]
    key_file = None if c["client_prefix"] == "anvil" else b.runtime(name) / "operator_key"
    approval = transaction(b, name, c, n["adminAddress"], n["tokenAddress"],
        calldata(b, c, "approve(address,uint256)", [n["bridgeAddress"], amount]), key_file=key_file)
    burn = transaction(b, name, c, n["adminAddress"], n["bridgeAddress"],
        calldata(b, c, "requestTransfer(uint256,address,uint256)", [destination["chainId"], recipient, amount]), key_file=key_file)
    topic = keccak(b, c, b"TransferInitiated(bytes32,uint256,address,address,address,address,address,uint256,uint256)".hex())
    logs = [log for log in burn["logs"] if log["address"].lower() == n["bridgeAddress"].lower() and log["topics"][0] == topic]
    if len(logs) != 1:
        raise b.BridgeError("Un événement de burn unique était attendu")
    result = {"transfer_id": logs[0]["topics"][1], "source": c["chain_id"], "amount": str(amount),
              "recipient": recipient, "approval_receipt": approval, "burn_receipt": burn}
    if confirm_source:
        result["source_confirmations"] = confirm_local_receipt(b, name, c, burn)
    return result


def await_mint(b, name, transfer, timeout=100):
    deployment = b.read_json(b.runtime(name) / "deployment.json")
    index = next(i for i, n in enumerate(deployment["networks"]) if n["chainId"] != transfer["source"])
    c, n = b.profile(name)["chains"][index], deployment["networks"][index]
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if int(call(b, c, n["bridgeAddress"], "processed(bytes32)", [transfer["transfer_id"]]), 16):
            topic = keccak(b, c, b"TransferCompleted(bytes32,address,uint256)".hex())
            logs = b.rpc(c["rpc_host"], "eth_getLogs", [{"address": n["bridgeAddress"], "fromBlock": hex(n["startBlock"]),
                           "toBlock": "latest", "topics": [topic, transfer["transfer_id"]]}])
            if len(logs) != 1:
                raise b.BridgeError("Le mint doit avoir exactement un événement canonique")
            r = receipt(b, c, logs[0]["transactionHash"])
            transfer["destination_confirmations"] = confirm_local_receipt(b, name, c, r)
            return r
        time.sleep(1)
    raise b.BridgeError("Mint non finalisé selon la politique locale dans le délai")


def demo(b, name):
    deployment = b.read_json(b.runtime(name) / "deployment.json")
    p = b.profile(name, runnable=True)
    before = [int(call(b, c, n["tokenAddress"], "balanceOf(address)", [n["adminAddress"]]), 16)
              for c, n in zip(p["chains"], deployment["networks"])]
    amount = 10 * 10**18
    forward = transfer(b, name, 0, amount)
    forward["mint_receipt"] = await_mint(b, name, forward)
    middle = [int(call(b, c, n["tokenAddress"], "balanceOf(address)", [n["adminAddress"]]), 16)
              for c, n in zip(p["chains"], deployment["networks"])]
    if middle != [before[0] - amount, before[1] + amount]:
        raise b.BridgeError("Soldes incorrects après aller")
    reverse = transfer(b, name, 1, amount)
    reverse["mint_receipt"] = await_mint(b, name, reverse)
    after = [int(call(b, c, n["tokenAddress"], "balanceOf(address)", [n["adminAddress"]]), 16)
             for c, n in zip(p["chains"], deployment["networks"])]
    supplies = [int(call(b, c, n["tokenAddress"], "totalSupply()"), 16)
                for c, n in zip(p["chains"], deployment["networks"])]
    if before != after or sum(supplies) != int(deployment["referenceSupply"]):
        raise b.BridgeError("Offre ou soldes non conservés au repos après aller-retour")
    result = {"utc": b.utc(), "profile": name, "passed": True, "before": list(map(str, before)),
              "middle": list(map(str, middle)), "after": list(map(str, after)), "supplies": list(map(str, supplies)),
              "forward": forward, "reverse": reverse,
              "scope": "Deux transferts réels, offre vérifiée au repos ; aucune émission externe ni transfert concurrent pendant ce contrôle"}
    b.write_json(b.LOCAL / (name + "-demo.json"), result)
    print(json.dumps({"roundtrip_passed": True, "profile": name, "transfer_ids": [forward["transfer_id"], reverse["transfer_id"]]}))
    return result


def application_isolation(b, name):
    policies = {
        "relayer": "test -r /run/secrets/bridge_db_password && test -r /run/secrets/signer_token && test ! -e /run/secrets/key_a && test ! -e /run/secrets/key_b && test ! -e /run/secrets/postgres_password",
        "signer": "test -r /run/secrets/key_a && test -r /run/secrets/key_b && test -r /run/secrets/signer_token && test ! -e /run/secrets/bridge_db_password && test ! -e /run/secrets/postgres_password",
        "postgres": "test -r /run/secrets/postgres_password && test -r /run/secrets/bridge_db_password && test ! -e /run/secrets/key_a && test ! -e /run/secrets/key_b && test ! -e /run/secrets/signer_token",
        "docs": "test ! -e /run/secrets/key_a && test ! -e /run/secrets/bridge_db_password && test ! -e /run/secrets/signer_token",
        "grafana": "test -r /run/secrets/grafana_password && test ! -e /run/secrets/key_a && test ! -e /run/secrets/bridge_db_password && test ! -e /run/secrets/signer_token",
    }
    result = {}
    for service, policy in policies.items():
        result[service] = b.compose(name, ["exec", "-T", service, "sh", "-ec", policy + " && test ! -e /var/run/docker.sock"])
    signer = b.container_id(name, "signer")
    ip = b.run(["docker", "inspect", "--format", "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}", signer])["stdout"]
    allowed = "import urllib.request; assert urllib.request.urlopen('http://signer:8080/health',timeout=3).status==200; print('signer health accessible')"
    result["signer_allowed"] = b.run(b.probe_args(name, "signing", allowed))
    denied = "import socket,sys\ntry:\n s=socket.create_connection((sys.argv[1],8080),3)\nexcept OSError:\n print('signer IP blocked from database network')\nelse:\n s.close(); raise SystemExit('forbidden route succeeded')"
    result["signer_denied"] = b.run(b.probe_args(name, "database", denied, [ip]))
    unauthenticated = "import urllib.request,urllib.error\nr=urllib.request.Request('http://signer:8080/sign',data=b'{}',headers={'Content-Type':'application/json'})\ntry:\n urllib.request.urlopen(r,timeout=3)\nexcept urllib.error.HTTPError as e:\n assert e.code==401; print('unauthenticated signing rejected')\nelse:\n raise SystemExit('unauthenticated signing accepted')"
    result["signer_authentication"] = b.run(b.probe_args(name, "signing", unauthenticated))
    return result


def resilience(b, name):
    import importlib.util
    spec = importlib.util.spec_from_file_location("bridge_resilience", b.ROOT / "tests/resilience.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.run(b, name)
    if not result["passed"]:
        raise b.BridgeError("Campagne de résilience en échec ; rapport .local/" + name + "-resilience.json")
    return result
