#!/usr/bin/env python3
"""Outillage du jalon 1. Aucun envoi de transaction ni signature de bridge."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import os
from pathlib import Path
import platform
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".local"
PROFILES = ("local-fast", "local-besu", "integration-testnet")
STATUSES = {"proposé", "implémenté", "vérifié_local", "vérifié_besu_local",
            "vérifié_sepolia", "vérifié_tela", "bloqué", "obsolète"}
REPORT_FILES = {"docs/claims.yaml", "docs/journal.md", "docs/resultats.md"}
RECORDS: list[dict] = []


class BridgeError(Exception):
    pass


def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def digest(data: bytes):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def run(args, *, check=True, timeout=60, env=None, transform=None):
    """Arguments structurés, sans shell ; ne jamais passer de secret dans args."""
    args = [str(x) for x in args]
    env = (os.environ.copy() if env is None else env.copy())
    env["PYTHONUTF8"] = "1"
    start = utc()
    try:
        p = subprocess.run(args, cwd=ROOT, env=env, capture_output=True, timeout=timeout,
                           encoding="utf-8", errors="replace")
        result = {"command": args, "utc": start, "exit_code": p.returncode,
                  "stdout": p.stdout.strip(), "stderr": p.stderr.strip()}
    except (OSError, subprocess.TimeoutExpired) as exc:
        result = {"command": args, "utc": start, "exit_code": 124 if isinstance(exc, subprocess.TimeoutExpired) else 127,
                  "stdout": "", "stderr": type(exc).__name__}
    if transform and result["exit_code"] == 0:
        result["stdout"] = transform(result["stdout"])
    RECORDS.append(result)
    if check and result["exit_code"] != 0:
        raise BridgeError(f"Échec ({result['exit_code']}) : {args[:5]}\n{result['stderr']}")
    return result


def lock():
    return read_json(ROOT / "sandbox/versions.lock.json")


def validate_profile(p):
    if p.get("name") not in PROFILES or p.get("test_only") is not True:
        raise BridgeError("Profil inconnu ou non réservé aux tests")
    if p["name"] == "integration-testnet":
        # Un booléen modifié ne peut pas activer une intégration non implémentée.
        if p.get("enabled") is not False:
            raise BridgeError("L'intégration doit rester désactivée au jalon 1")
        return
    expected = {"local-fast": [31337, 31338], "local-besu": [31339, 31340]}[p["name"]]
    if [c["chain_id"] for c in p["chains"]] != expected:
        raise BridgeError("Chain IDs hors de la paire locale explicitement autorisée")
    if p.get("evm_target") != "london" or p.get("token_decimals") != 18:
        raise BridgeError("Cible EVM ou decimals non pris en charge")
    for c in p["chains"]:
        if not re.fullmatch(r"http://127\.0\.0\.1:[0-9]+", c["rpc_host"]):
            raise BridgeError("RPC externe interdit pour un profil local")
        if not c.get("finality") or c["finality"].get("mode") not in ("confirmations", "qbft-local"):
            raise BridgeError("Politique de finalité absente ou inconnue")
        mode = c["finality"]["mode"]
        if c["client_prefix"] == "anvil" and mode != "confirmations":
            raise BridgeError("Anvil exige une politique explicite de confirmations")
        if c["client_prefix"] == "besu" and mode != "qbft-local":
            raise BridgeError("Ce profil Besu exige qbft-local")
        if mode == "confirmations":
            depth = c["finality"].get("depth")
            if type(depth) is not int or not 1 <= depth <= 128:
                raise BridgeError("Nombre de confirmations invalide")


def profile(name, runnable=False):
    if name not in PROFILES:
        raise BridgeError("Profil inconnu")
    p = read_json(ROOT / f"sandbox/profiles/{name}.json")
    validate_profile(p)
    if runnable and name == "integration-testnet":
        raise BridgeError("Intégration désactivée : consulter docs/informations-manquantes.md (TELA-01..06, SEP-01..02, SEC-01)")
    return p


def project(name):
    profile(name, runnable=True)
    return "t3l4n-bridge-" + name


def runtime(name):
    profile(name, runnable=True)
    return LOCAL / "runtime" / name


def compose(name, args, **kwargs):
    p = profile(name, runnable=True)
    env = os.environ.copy()
    for key in list(env):
        if key.startswith("COMPOSE_"):
            env.pop(key)
    env.update({key.upper() + "_IMAGE": value for key, value in lock()["images"].items()})
    env.update(BRIDGE_ROOT=ROOT.as_posix(), BRIDGE_RUNTIME=runtime(name).as_posix(),
               DOCS_PORT=str(p["docs_port"]), RPC_A_PORT=str(urlparse(p["chains"][0]["rpc_host"]).port),
               RPC_B_PORT=str(urlparse(p["chains"][1]["rpc_host"]).port),
               NETWORK_PREFIX="10.231.240" if name == "local-fast" else "10.231.241")
    LOCAL.mkdir(exist_ok=True)
    empty = LOCAL / "compose.empty.env"
    empty.write_text("# Pas de chargement implicite de .env\n", encoding="utf-8")
    base = ["docker", "compose", "--project-name", project(name), "--env-file", empty]
    for f in p["compose_files"]:
        base += ["-f", ROOT / f]
    return run(base + args, env=env, **kwargs)


def source_snapshot():
    output = run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"])["stdout"]
    names = sorted(set(output.split("\0")) - {""})
    files = {}
    for name in names:
        if name.startswith("evidence/") or name in REPORT_FILES:
            continue
        path = ROOT / name
        if path.is_file():
            files[name] = digest(path.read_bytes())
        else:
            files[name] = "deleted"
    return {"sha256": digest(canonical(files)), "files": files,
            "excluded_reporting_paths": sorted(REPORT_FILES) + ["evidence/**"]}


def registry():
    # JSON est un sous-ensemble de YAML 1.2 ; pas de parseur supplémentaire au runtime.
    return read_json(ROOT / "docs/claims.yaml")


def claim_definition(c):
    return {k: c[k] for k in ("id", "statement", "scope", "hypotheses", "code", "verification", "environment", "expected")}


def effective_status(c, snapshot):
    if not c["status"].startswith("vérifié_"):
        return c["status"]
    ref = c.get("evidence")
    if not ref:
        return "obsolète"
    path = (ROOT / ref).resolve()
    if not path.is_relative_to((ROOT / "evidence").resolve()) or not path.is_file():
        return "obsolète"
    try:
        m = verify_evidence(path)
    except (BridgeError, OSError, ValueError, KeyError, TypeError):
        return "obsolète"
    statuses = {"local-fast": "vérifié_local", "local-besu": "vérifié_besu_local"}
    try:
        valid = (m["source"]["sha256"] == snapshot["sha256"] and
                 m.get("profile") == c["environment"] and
                 statuses.get(m.get("profile")) == c["status"] and
                 m.get("claim_definitions", {}).get(c["id"]) == digest(canonical(claim_definition(c))) and
                 any(check["id"] == c["verification"] and check["passed"] is True for check in m["checks"]))
    except (KeyError, TypeError):
        valid = False
    return c["status"] if valid else "obsolète"


def verify_evidence(path):
    path = Path(path).resolve()
    checksum = path.with_name("manifest.sha256").read_text(encoding="utf-8")
    if not re.fullmatch(r"[0-9a-f]{64}  manifest\.json\s*", checksum):
        raise BridgeError("Fichier d'empreinte invalide")
    expected = checksum.split()[0]
    if digest(path.read_bytes()) != expected:
        raise BridgeError("Empreinte du manifeste invalide")
    m = read_json(path)
    for name, sha in m["artifacts"].items():
        artifact = (path.parent / name).resolve()
        if not artifact.is_relative_to(path.parent) or not artifact.is_file() or digest(artifact.read_bytes()) != sha:
            raise BridgeError("Artefact absent, sortant ou altéré")
    return m


def docs_build():
    python = ROOT / (".venv/Scripts/python.exe" if os.name == "nt" else ".venv/bin/python")
    if not python.exists():
        raise BridgeError("MkDocs absent : lancer bootstrap (phase installation)")
    result = run([python, "-m", "mkdocs", "build", "--strict"], timeout=60)
    target = ROOT / "site/evidence"
    if (ROOT / "evidence").exists():
        shutil.copytree(ROOT / "evidence", target, dirs_exist_ok=True)
    return result


def bootstrap(name, docs_only=False):
    profile(name, runnable=True)
    LOCAL.mkdir(exist_ok=True)
    python = ROOT / (".venv/Scripts/python.exe" if os.name == "nt" else ".venv/bin/python")
    if not python.exists():
        run([sys.executable, "-m", "venv", ROOT / ".venv"], timeout=60)
    run([python, "-m", "pip", "--disable-pip-version-check", "install", "--require-hashes", "-r", "requirements-docs.lock"], timeout=240)
    if docs_only:
        return
    keys = ["foundry", "postgres", "probe", "gitleaks"]
    if name == "local-besu":
        keys += ["besu"]
    for key in keys:
        print(f"Installation : image {key}", flush=True)
        run(["docker", "pull", "--platform", "linux/amd64", lock()["images"][key]], timeout=300)
    target = runtime(name)
    target.mkdir(parents=True, exist_ok=True)
    target.chmod(0o700)
    password = target / "postgres_password"
    if not password.exists():
        password.write_text(secrets.token_urlsafe(40), encoding="utf-8")
        # Compose file secrets conserve les permissions du bind, pas uid/gid Swarm.
        # Le répertoire parent 0700 borne l'accès hôte ; seul postgres reçoit ce fichier.
        password.chmod(0o444)
    (target / "signer_witness").write_text("TEMOIN SANS SECRET REEL\n", encoding="utf-8")
    if name == "local-besu" and not (target / "genesis.json").exists():
        generated = target / "generated"
        generated.mkdir(exist_ok=True)
        generated.chmod(0o777)  # Sortie temporaire locale, sans publication ; resserrée ensuite.
        run(["docker", "run", "--rm", "--network", "none", "--user", "1000:1000",
             "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true", "--read-only",
             "--memory", "1g", "--cpus", "2", "--pids-limit", "256", "--tmpfs", "/tmp:rw,nosuid,size=64m",
             "-v", f"{ROOT / 'sandbox/besu/qbft.json'}:/config/qbft.json:ro",
             "-v", f"{generated}:/output", lock()["images"]["besu"], "operator", "generate-blockchain-config",
             "--config-file=/config/qbft.json", "--to=/output", "--private-key-file-name=key"], timeout=120)
        nodekeys = list((generated / "keys").glob("*/key"))
        if len(nodekeys) != 1:
            raise BridgeError("Génération QBFT : nombre de clés inattendu")
        shutil.copyfile(generated / "genesis.json", target / "genesis.json")
        shutil.copyfile(nodekeys[0], target / "besu_node_key")
        (target / "besu_node_key").chmod(0o444)
        generated.chmod(0o700)
    docs_build()


def rpc(url, method, params=None):
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []}).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    # Les RPC locaux ne doivent pas traverser un proxy configuré sur l'hôte.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=5) as resp:
        result = json.load(resp)
    if result.get("id") != 1 or result.get("error") or "result" not in result:
        raise BridgeError(f"RPC {method} incohérent ou en erreur")
    return result["result"]


def chain_observation(c):
    chain_id = int(rpc(c["rpc_host"], "eth_chainId"), 16)
    client = rpc(c["rpc_host"], "web3_clientVersion")
    if chain_id != c["chain_id"] or c["client_prefix"] not in client.lower():
        raise BridgeError("Identité du nœud inattendue : refus")
    genesis = rpc(c["rpc_host"], "eth_getBlockByNumber", ["0x0", False])
    block = rpc(c["rpc_host"], "eth_getBlockByNumber", ["latest", False])
    if not genesis or not block:
        raise BridgeError("RPC sans bloc genesis ou latest")
    return {"chain_id": chain_id, "client": client, "genesis_hash": genesis["hash"],
            "head": int(block["number"], 16), "head_hash": block["hash"]}


def up(name):
    p = profile(name, runnable=True)
    validate_compose(name)
    if not (runtime(name) / "postgres_password").is_file():
        raise BridgeError("Configuration locale absente : lancer bootstrap")
    if not (ROOT / "site/index.html").is_file():
        docs_build()
    # Jamais de pull implicite dans la phase d'exécution.
    compose(name, ["up", "--detach", "--pull", "never", "--force-recreate", "--wait", "--wait-timeout", "90"], timeout=120)
    deadline = time.monotonic() + 60
    while True:
        try:
            observed = [chain_observation(c) for c in p["chains"]]
            print(json.dumps({"profile": name, "infra_ready": True, "bridge_implemented": False, "chains": observed}, ensure_ascii=False))
            return observed
        except Exception:
            if time.monotonic() >= deadline:
                raise BridgeError("Les RPC n'ont pas fourni les identités attendues dans le délai")
            time.sleep(2)


def doctor(offline=False):
    report = {"utc": utc(), "platform": platform.platform(), "cpu_logical": os.cpu_count(),
              "disk_free_gib": round(shutil.disk_usage(ROOT).free / 2**30, 2), "tools": {},
              "session_declaration": "Lancement initial : danger-full-access, réseau activé, approval never ; pas une preuve de confinement."}
    for tool, args in {"git": ["--version"], "docker": ["version", "--format", "{{json .}}"],
                       "dotnet": ["--list-sdks"], "python": ["--version"], "forge": ["--version"],
                       "anvil": ["--version"], "cast": ["--version"], "uv": ["--version"],
                       "node": ["--version"], "java": ["-version"], "podman": ["--version"]}.items():
        exe = shutil.which(tool)
        report["tools"][tool] = run([exe or tool, *args], check=False, timeout=15)
    report["compose"] = run(["docker", "compose", "version"], check=False)
    report["docker_context"] = run(["docker", "context", "show"], check=False)["stdout"]
    report["docker_info"] = run(["docker", "info", "--format", "{{json .}}"], check=False, transform=lambda raw: json.dumps({
        k: v for k, v in json.loads(raw).items() if k in {"OSType", "Architecture", "NCPU", "MemTotal", "SecurityOptions", "ContainersRunning", "ServerVersion", "MemoryLimit", "PidsLimit", "CpuCfsQuota"}}))
    nets = run(["docker", "network", "ls", "--quiet"], check=False)
    report["docker_subnets"] = []
    if nets["exit_code"] == 0:
        for network_id in nets["stdout"].splitlines():
            report["docker_subnets"].append(run(["docker", "network", "inspect", network_id, "--format", "{{json .IPAM.Config}}"], check=False)["stdout"])
    if os.name == "nt":
        report["host_policy"] = run(["powershell", "-NoProfile", "-Command",
            "$os=Get-CimInstance Win32_OperatingSystem; [pscustomobject]@{language_mode=[string]$ExecutionContext.SessionState.LanguageMode; memory_free_kib=$os.FreePhysicalMemory; memory_total_kib=$os.TotalVisibleMemorySize; is_admin=([System.Security.Principal.WindowsPrincipal]::new([System.Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator))} | ConvertTo-Json -Compress"], check=False)
        report["host_ipv4_routes"] = run(["powershell", "-NoProfile", "-Command", "Get-NetRoute -AddressFamily IPv4 | Select-Object -ExpandProperty DestinationPrefix | ConvertTo-Json -Compress"], check=False)
    else:
        report["host_ipv4_routes"] = run(["ip", "-j", "-4", "route"], check=False)
    with tempfile.TemporaryDirectory(prefix="t3l4n-host-witness-") as d:
        witness = Path(d) / "non-sensitive.txt"
        witness.write_text("TEMOIN SANS DONNEES SENSIBLES", encoding="utf-8")
        probe = run([sys.executable, "-c", "import pathlib,sys; print(pathlib.Path(sys.argv[1]).read_text() == 'TEMOIN SANS DONNEES SENSIBLES')", witness])
        report["host_child_can_read_outside_workspace"] = probe["stdout"] == "True"
    report["network_installation"] = []
    if not offline:
        for url in ("https://github.com", "https://pypi.org/simple/mkdocs/", "https://api.nuget.org/v3/index.json"):
            try:
                with urllib.request.urlopen(url, timeout=10) as resp:
                    code = resp.status
                report["network_installation"].append({"url": url, "http_status": code})
            except Exception as exc:
                report["network_installation"].append({"url": url, "error": type(exc).__name__})
    report["limitations"] = ["Hôte et moteur Docker partagés, pas de VM dédiée attestée", "Aucun filtrage de destinations imposé au processus hôte", "Accès au moteur Docker réservé par convention à l'orchestrateur, pas par ACL projet", "Les outils applicatifs futurs ne sont pas tous installés"]
    write_json(LOCAL / "doctor.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def lint():
    for name in PROFILES:
        profile(name)
    for value in lock()["images"].values():
        if not re.search(r"@sha256:[0-9a-f]{64}$", value):
            raise BridgeError("Image non épinglée par empreinte")
    seen = set()
    for c in registry()["claims"]:
        if c["id"] in seen or c["status"] not in STATUSES:
            raise BridgeError("Identifiant dupliqué ou statut invalide dans le registre")
        seen.add(c["id"])
        claim_definition(c)
        for path in c["code"]:
            if not (ROOT / path).exists():
                raise BridgeError(f"Référence de code absente : {path}")
    print(f"Registre : {len(seen)} affirmations ; trois profils valides")


def validate_compose(name):
    config = json.loads(compose(name, ["--profile", "isolation", "config", "--format", "json"])["stdout"])
    for service, cfg in config["services"].items():
        if str(cfg.get("user", "0")).split(":")[0] in ("0", "root"):
            raise BridgeError(f"Service root : {service}")
        if not cfg.get("read_only") or cfg.get("privileged") or cfg.get("cap_add") or "ALL" not in cfg.get("cap_drop", []):
            raise BridgeError(f"Restrictions incomplètes : {service}")
        if not any("no-new-privileges" in s for s in cfg.get("security_opt", [])):
            raise BridgeError(f"Escalade non interdite : {service}")
        if not all(cfg.get(k) for k in ("mem_limit", "cpus", "pids_limit", "logging")):
            raise BridgeError(f"Limites absentes : {service}")
        if cfg.get("image") not in lock()["images"].values():
            raise BridgeError(f"Image hors verrou : {service}")
        for port in cfg.get("ports", []):
            if port.get("host_ip") != "127.0.0.1":
                raise BridgeError(f"Port non loopback : {service}")
        for mount in cfg.get("volumes", []):
            if mount.get("type") == "bind":
                allowed = {"docs": [((ROOT / "site").resolve(), "/site")],
                           "rpc-a": [((ROOT / "sandbox/loopback_proxy.py").resolve(), "/app/proxy.py")],
                           "rpc-b": [((ROOT / "sandbox/loopback_proxy.py").resolve(), "/app/proxy.py")],
                           "docs-gateway": [((ROOT / "sandbox/loopback_proxy.py").resolve(), "/app/proxy.py")],
                           "chain-a": [((runtime(name) / "genesis.json").resolve(), "/config/genesis.json")]}
                if (Path(mount.get("source", "")).resolve(), mount.get("target")) not in allowed.get(service, []) or not mount.get("read_only"):
                    raise BridgeError(f"Montage hors liste autorisée : {service}")
    for net, cfg in config["networks"].items():
        if net.startswith("edge_"):
            if cfg.get("driver_opts", {}).get("com.docker.network.bridge.enable_ip_masquerade") != "false":
                raise BridgeError("NAT sortant non désactivé sur le réseau de consultation")
        elif not cfg.get("internal"):
            raise BridgeError("Réseau métier local non interne")
    return config


def run_tests():
    lint()
    result = run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"], timeout=60)
    print(result["stderr"] or result["stdout"])
    return result


def scan_secrets():
    # Uniquement les fichiers versionnables ; aucun montage de .local ni des clés.
    with tempfile.TemporaryDirectory(prefix="t3l4n-scan-") as d:
        Path(d).chmod(0o755)  # Copie des seules sources versionnables, lisible par uid10001.
        output = run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"])["stdout"]
        for name in set(output.split("\0")) - {""}:
            src = ROOT / name
            if src.is_file():
                dst = Path(d) / name
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dst)
        scanner = ["docker", "run", "--rm", "--pull", "never", "--network", "none", "--read-only",
                      "--user", "10001:10001", "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
                      "--memory", "256m", "--cpus", "1", "--pids-limit", "64", "-v", f"{d}:/scan:ro",
                      lock()["images"]["gitleaks"], "dir"]
        options = ["--config", "/scan/.gitleaks.toml", "--redact", "--no-banner", "--verbose"]
        result = run(scanner + ["/scan", *options], timeout=60)
        # Faux credential sans validité, créé exclusivement dans la copie temporaire.
        # Le contrôle assure que l'exception d'empreinte ne masque pas les vrais motifs.
        control = Path(d) / "evidence/scan-control/manifest.json"
        write_json(control, {"api_key": "ghp_" + "".join(secrets.choice("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789") for _ in range(36))})
        detection = run(scanner + ["/scan/evidence/scan-control", *options], timeout=60, check=False)
        if detection["exit_code"] != 1:
            raise BridgeError("Le contrôle positif du détecteur n'a pas reconnu le credential synthétique")
    return {"project_scan": result, "synthetic_positive_control": detection}


def status(name):
    p = profile(name)
    snapshot = source_snapshot()
    commit_result = run(["git", "rev-parse", "HEAD"], check=False)
    state = {"utc": utc(), "mode": "instantané historique ; rafraîchir avec status", "profile": name,
             "code_commit": commit_result["stdout"] if commit_result["exit_code"] == 0 else None,
             "source_sha256": snapshot["sha256"], "bridge": "non implémenté (jalon 2)", "services": [], "chains": []}
    if name != "integration-testnet":
        r = compose(name, ["ps", "--all", "--format", "json"], check=False)
        if r["exit_code"] == 0 and r["stdout"]:
            raw = r["stdout"]
            records = json.loads(raw) if raw.startswith("[") else [json.loads(line) for line in raw.splitlines()]
            state["services"] = [{"name": s["Service"], "state": s["State"], "health": s.get("Health", "")} for s in records]
        for c in p["chains"]:
            try:
                state["chains"].append(chain_observation(c))
            except Exception:
                state["chains"].append({"chain_id": c["chain_id"], "status": "arrêté ou RPC indisponible"})
    state["claims"] = [{"id": c["id"], "status": effective_status(c, snapshot), "evidence": c.get("evidence")} for c in registry()["claims"]]
    campaigns = sorted((ROOT / "evidence").glob("*/manifest.json"))
    state["last_campaign"] = str(campaigns[-1].relative_to(ROOT)).replace("\\", "/") if campaigns else None
    write_json(LOCAL / "status.json", state)
    page = ROOT / "site/status/index.html"
    page.parent.mkdir(parents=True, exist_ok=True)
    rows = "".join(f"<tr><td>{html.escape(c['id'])}</td><td>{html.escape(c['status'])}</td><td>" + (f"<a href='../../{html.escape(c['evidence'])}'>preuve JSON</a>" if c["evidence"] else "aucune") + "</td></tr>" for c in state["claims"])
    page.write_text("<!doctype html><html lang='fr'><meta charset='utf-8'><meta name='viewport' content='width=device-width'><title>État T3l4N Bridge</title><style>body{font:16px system-ui;max-width:70rem;margin:2rem auto;padding:1rem}td,th{padding:.6rem;border-bottom:1px solid #bbb;text-align:left}pre{white-space:pre-wrap}aside{background:#fff0c0;padding:1rem}</style><h1>État du projet</h1><aside>Instantané historique, aucune actualisation automatique. Les services peuvent avoir changé depuis ce relevé. Dernière mise à jour UTC : " + state["utc"] + "</aside><p><a href='../'>Documentation</a></p><p>Bridge : non implémenté. Les métriques de transferts, de gas, de pause et de réconciliation sont indisponibles.</p><h2>Exploitation observée</h2><pre>" + html.escape(json.dumps({k: state[k] for k in ("profile", "code_commit", "source_sha256", "services", "chains", "last_campaign")}, ensure_ascii=False, indent=2)) + "</pre><h2>Affirmations</h2><table><tr><th>ID</th><th>Statut effectif</th><th>Preuve</th></tr>" + rows + "</table></html>", encoding="utf-8")
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return state


def probe_args(name, network, code, args=(), mounts=()):
    return ["docker", "run", "--rm", "--pull", "never", "--label", f"com.t3l4n.project={project(name)}",
            "--network", f"{project(name)}_{network}", "--user", "10001:10001", "--read-only", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges:true", "--memory", "64m", "--cpus", "0.5", "--pids-limit", "32",
            *mounts, lock()["images"]["probe"], "python", "-c", code, *args]


def container_id(name, service):
    value = compose(name, ["ps", "--quiet", service])["stdout"]
    if not re.fullmatch(r"[0-9a-f]{12,64}", value):
        raise BridgeError("Identifiant de conteneur absent ou ambigu")
    return value


def prove(name):
    profile(name, runnable=True)
    commit = run(["git", "rev-parse", "HEAD"])["stdout"]
    snapshot = source_snapshot()
    campaign = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + name
    out = ROOT / "evidence" / campaign
    out.mkdir(parents=True, exist_ok=False)
    manifest = {"schema_version": 1, "campaign": campaign, "utc_start": utc(), "source_commit": commit,
                "git_status": run(["git", "status", "--porcelain=v1", "--untracked-files=all"])["stdout"],
                "source": snapshot, "profile": name, "configuration": profile(name), "versions_lock": lock(),
                "claim_definitions": {c["id"]: digest(canonical(claim_definition(c))) for c in registry()["claims"]},
                "checks": [], "not_executed": ["transferts ERC20", "reprise du relayer", "fuzzing et invariants du bridge", "réconciliation de l'offre", "intégration Sepolia", "intégration TELA"],
                "retention": "Manifestes et rapports légers : durée de vie du dépôt ; données locales et site : jusqu'au nettoyage explicite par le propriétaire"}

    def check(id_, expected, function):
        print(f"Vérification : {id_}", flush=True)
        try:
            observed = function()
            passed = True
        except Exception as exc:
            passed, observed = False, str(exc)
        manifest["checks"].append({"id": id_, "expected": expected, "observed": observed, "passed": passed, "utc": utc()})
        return passed

    try:
        check("tooling", "Tous les tests d'outillage réussissent", run_tests)
        check("capabilities", "Au moins 50 agents et 50 skills distincts et valides", lambda: run([sys.executable, "scripts/validate_capabilities.py"]))
        check("compose", "Deux configurations Compose valides, durcies et sans port public", lambda: {p: validate_compose(p) for p in ("local-fast", "local-besu")})
        check("docs", "Construction MkDocs stricte réussie", docs_build)
        check("secrets", "Gitleaks : aucun secret détecté dans les fichiers versionnables", scan_secrets)
        ready = check("startup", "Deux chain IDs attendus répondent ; aucune preuve de transfert", lambda: up(name))
        if ready:
            check("hardening", "Restrictions réellement appliquées aux services et passerelles", lambda: inspect_runtime(name))
            check("isolation", "Communication permise réussie ; IP inter-réseau, fichiers et secrets interdits inaccessibles", lambda: isolation(name))
            check("persistence", "Témoin SQL et progression de bloc conservés après down/up du projet", lambda: persistence(name))
        check("integration_gate", "Intégration refusée avant toute commande Docker ou RPC", integration_gate)
        check("source_unchanged", "Empreinte des sources inchangée pendant la campagne", lambda: assert_equal(source_snapshot()["sha256"], snapshot["sha256"]))
    finally:
        manifest["utc_end"] = utc()
        manifest["passed"] = bool(manifest["checks"]) and all(c["passed"] for c in manifest["checks"])
        manifest["tool_versions"] = {"python": platform.python_version(), "git": run(["git", "--version"])["stdout"], "compose": run(["docker", "compose", "version"], check=False)["stdout"]}
        manifest["images_used"] = image_observations(name)
        if name == "local-besu" and (runtime(name) / "genesis.json").is_file():
            shutil.copyfile(runtime(name) / "genesis.json", out / "besu-genesis.json")
        python = ROOT / (".venv/Scripts/python.exe" if os.name == "nt" else ".venv/bin/python")
        manifest["installed_docs_dependencies"] = run([python, "-m", "pip", "freeze"], check=False)["stdout"]
        for report in ("skills-quick-validation.json", "capabilities-validator-tests.json", "skills-forward-review.json"):
            if (LOCAL / report).is_file():
                shutil.copyfile(LOCAL / report, out / report)
        if (LOCAL / "doctor.json").is_file():
            shutil.copyfile(LOCAL / "doctor.json", out / "doctor.json")
        write_json(out / "commands.json", RECORDS)
        manifest["artifacts"] = {p.name: digest(p.read_bytes()) for p in out.iterdir() if p.is_file()}
        write_json(out / "manifest.json", manifest)
        (out / "manifest.sha256").write_text(digest((out / "manifest.json").read_bytes()) + "  manifest.json\n", encoding="utf-8")
        print(f"Preuve : {out.relative_to(ROOT).as_posix()}/manifest.json ; réussite={manifest['passed']}")
    if not manifest["passed"]:
        raise BridgeError("Campagne en échec ; consulter les résultats conservés")


def assert_equal(observed, expected):
    if observed != expected:
        raise BridgeError(f"Attendu {expected}, observé {observed}")
    return observed


def integration_gate():
    before = len(RECORDS)
    try:
        up("integration-testnet")
    except BridgeError as exc:
        if len(RECORDS) != before:
            raise BridgeError("Une commande a été lancée avant le refus")
        return str(exc)
    raise BridgeError("Le profil d'intégration a été accepté à tort")


def inspect_runtime(name):
    observations = {}
    for service in ("chain-a", "chain-b", "postgres", "docs", "rpc-a", "rpc-b", "docs-gateway"):
        cid = container_id(name, service)
        raw = json.loads(run(["docker", "inspect", cid], transform=lambda s: json.dumps([
            {"Config": {"User": x["Config"]["User"], "Image": x["Config"]["Image"]},
             "HostConfig": {k: x["HostConfig"][k] for k in ("ReadonlyRootfs", "Privileged", "CapDrop", "SecurityOpt", "Memory", "NanoCpus", "PidsLimit", "PortBindings", "LogConfig")},
             "Mounts": x["Mounts"]} for x in json.loads(s)])) ["stdout"])[0]
        h = raw["HostConfig"]
        if not (h["ReadonlyRootfs"] and not h["Privileged"] and "ALL" in h["CapDrop"] and h["Memory"] > 0 and h["NanoCpus"] > 0 and h["PidsLimit"] > 0 and any("no-new-privileges" in v for v in h["SecurityOpt"])):
            raise BridgeError(f"Durcissement absent sur {service}")
        if raw["Config"]["User"].split(":")[0] in ("", "0", "root"):
            raise BridgeError("Utilisateur root effectif configuré")
        observations[service] = raw
    return observations


def isolation(name):
    results = {}
    # Témoin de signature, pas un service de signature fonctionnel.
    compose(name, ["--profile", "isolation", "up", "-d", "--pull", "never", "--wait", "witness-signer"], timeout=60)
    try:
        witness = container_id(name, "witness-signer")
        ip = run(["docker", "inspect", "--format", "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}", witness])["stdout"]
        permitted = "import urllib.request; r=urllib.request.urlopen('http://witness-signer:8080/',timeout=3); assert r.status==200; print('HTTP 200')"
        results["allowed_same_network"] = run(probe_args(name, "signing", permitted))
        # Contrôle positif sur l'IP, puis tentative depuis un autre réseau : pas un simple échec DNS.
        tcp_success = "import socket,sys; s=socket.create_connection((sys.argv[1],8080),3); s.close(); print('TCP OK')"
        results["target_ip_positive_control"] = run(probe_args(name, "signing", tcp_success, [ip]))
        tcp_blocked = "import socket,sys\ntry:\n s=socket.create_connection((sys.argv[1],8080),3)\nexcept OSError as e:\n print(type(e).__name__)\nelse:\n s.close(); raise SystemExit('Communication interdite reussie')"
        results["forbidden_cross_network_by_ip"] = run(probe_args(name, "database", tcp_blocked, [ip]))
        secret_paths = "from pathlib import Path; assert not Path('/run/secrets/postgres_password').exists(); assert not Path('/run/secrets/signer_witness').exists(); assert not Path('/var/run/docker.sock').exists(); print('secrets et socket absents')"
        results["probe_no_secrets"] = run(probe_args(name, "database", secret_paths))
        results["signer_only_own_witness"] = compose(name, ["exec", "-T", "witness-signer", "python", "-c", "from pathlib import Path; assert Path('/run/secrets/signer_witness').read_text().startswith('TEMOIN'); assert not Path('/run/secrets/postgres_password').exists(); print('temoin propre lisible, secret base absent')"])
        results["postgres_no_signer_secret"] = compose(name, ["exec", "-T", "postgres", "sh", "-c", "test -r /run/secrets/postgres_password && test ! -e /run/secrets/signer_witness"])
        with tempfile.TemporaryDirectory(prefix="t3l4n-outside-") as d:
            Path(d).chmod(0o755)
            marker = Path(d) / "witness.txt"
            marker.write_text("TEMOIN PUBLIC", encoding="utf-8")
            control = "from pathlib import Path; assert Path('/control/witness.txt').read_text()=='TEMOIN PUBLIC'; print('temoin existe')"
            results["file_positive_control"] = run(probe_args(name, "database", control, mounts=["-v", f"{d}:/control:ro"]))
            denied = "from pathlib import Path; import sys; assert not Path('/control/witness.txt').exists(); assert not Path(sys.argv[1]).exists(); print('temoin hors perimetre inaccessible')"
            results["outside_file_absent_without_mount"] = run(probe_args(name, "database", denied, [str(marker)]))
        hard = "from pathlib import Path; import os; assert os.geteuid()!=0; s=Path('/proc/self/status').read_text(); assert 'CapEff:\\t0000000000000000' in s; assert 'NoNewPrivs:\\t1' in s\ntry:\n Path('/write-forbidden').write_text('temoin')\nexcept OSError:\n print('non root, sans capacites, no-new-privileges, racine non inscriptible')\nelse:\n raise SystemExit('racine inscriptible')"
        results["process_boundaries"] = run(probe_args(name, "database", hard))
    finally:
        compose(name, ["--profile", "isolation", "stop", "witness-signer"], check=False)
        compose(name, ["--profile", "isolation", "rm", "--force", "witness-signer"], check=False)
    return results


def persistence(name):
    marker = "campaign_" + str(time.time_ns())
    sql = f"CREATE TABLE IF NOT EXISTS sandbox_probe (id text PRIMARY KEY); INSERT INTO sandbox_probe VALUES ('{marker}');"
    compose(name, ["exec", "-T", "postgres", "psql", "-U", "sandbox_admin", "-d", "bridge", "-v", "ON_ERROR_STOP=1", "-c", sql])
    before = [chain_observation(c) for c in profile(name)["chains"]]
    compose(name, ["down", "--timeout", "20"], timeout=60)
    after = up(name)
    count = compose(name, ["exec", "-T", "postgres", "psql", "-U", "sandbox_admin", "-d", "bridge", "-At", "-v", "ON_ERROR_STOP=1", "-c", f"SELECT count(*) FROM sandbox_probe WHERE id='{marker}';"])["stdout"]
    assert_equal(count, "1")
    for a, b in zip(before, after):
        assert_equal(b["genesis_hash"], a["genesis_hash"])
        if b["head"] < a["head"]:
            raise BridgeError("Recul de hauteur après redémarrage")
    return {"sql_marker_rows": 1, "before": before, "after": after, "scope": "Volumes et témoin SQL seulement, aucun état de relayer"}


def image_observations(name):
    keys = ["foundry", "postgres", "probe", "gitleaks"] + (["besu"] if name == "local-besu" else [])
    observed = {}
    for key in keys:
        r = run(["docker", "image", "inspect", lock()["images"][key], "--format", "{{json .}}"], check=False,
                transform=lambda raw: json.dumps({k: v for k, v in json.loads(raw).items() if k in ("Id", "RepoDigests", "Architecture", "Os")}))
        observed[key] = r
    return observed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for cmd in ("doctor", "bootstrap", "up", "down", "status", "test", "prove", "docs", "lint", "scan", "config"):
        p = sub.add_parser(cmd)
        p.add_argument("--profile", choices=PROFILES, default="local-fast")
        if cmd == "doctor":
            p.add_argument("--offline", action="store_true")
        if cmd == "bootstrap":
            p.add_argument("--docs-only", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "doctor":
            r = doctor(args.offline)
            return 0 if r["tools"]["docker"]["exit_code"] == 0 else 2
        if args.command == "bootstrap":
            bootstrap(args.profile, args.docs_only)
        elif args.command == "up":
            up(args.profile)
            status(args.profile)
        elif args.command == "down":
            compose(args.profile, ["--profile", "isolation", "down", "--timeout", "20"], timeout=60)
            status(args.profile)
        elif args.command == "status":
            status(args.profile)
        elif args.command == "test":
            run_tests()
        elif args.command == "prove":
            prove(args.profile)
        elif args.command == "docs":
            docs_build()
            status(args.profile)
        elif args.command == "lint":
            lint()
        elif args.command == "scan":
            scan_secrets()
        elif args.command == "config":
            config = validate_compose(args.profile)
            print(json.dumps(config, ensure_ascii=False, indent=2))
        return 0
    except (BridgeError, ValueError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    exit_code = 1
    try:
        exit_code = main()
    finally:
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        write_json(LOCAL / "history" / (stamp + ".json"), {"utc": utc(), "argv": sys.argv[1:], "exit_code": exit_code, "commands": RECORDS})
    sys.exit(exit_code)
