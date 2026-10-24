#!/usr/bin/env python3
"""Build and test contracts in the pinned offline Foundry container; retain JSON evidence."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parent
IMAGE = "ghcr.io/foundry-rs/foundry:v1.3.1@sha256:2dbf3d0fc58593ad9d01ef57677f93f83f4987acd295d17f303448d82e3a3ae7"
SEED = "0x20261024"
EXCLUDED = {".toolchain", ".artifacts", "out", "cache", "__pycache__"}


def utc():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def snapshot():
    return {p.relative_to(ROOT).as_posix(): sha256(p.read_bytes()) for p in sorted(ROOT.rglob("*"))
            if p.is_file() and not any(part in EXCLUDED for part in p.relative_to(ROOT).parts)}


def compiled_artifacts():
    """Exact files plus canonical ABI and decoded bytecode fingerprints, never deployment guesses."""
    artifacts = {}
    for name in ("Bridge", "BridgeToken"):
        relative = "out/" + name + ".sol/" + name + ".json"
        raw = (ROOT / relative).read_bytes()
        artifact = json.loads(raw)
        metadata = artifact["metadata"]
        artifacts[relative] = {
            "sha256": sha256(raw),
            "abi_sha256": sha256(json.dumps(artifact["abi"], sort_keys=True, separators=(",", ":"),
                                           ensure_ascii=False).encode("utf-8")),
            "abi_encoding": "UTF-8 JSON, sort_keys=true, separators=(',', ':'), ensure_ascii=false; no trailing newline",
            "creation_bytecode_sha256": sha256(bytes.fromhex(artifact["bytecode"]["object"].removeprefix("0x"))),
            "runtime_template_sha256": sha256(bytes.fromhex(artifact["deployedBytecode"]["object"].removeprefix("0x"))),
            "runtime_template_limit": "Bridge constructor immutables are placeholders; deployed code hash must be read on-chain",
            "compiler": metadata["compiler"]["version"],
            "evm_version": metadata["settings"]["evmVersion"],
            "optimizer": metadata["settings"]["optimizer"],
            "metadata_settings": metadata["settings"].get("metadata", {}),
        }
    return artifacts


def execute(command, timeout=240):
    started = utc()
    tick = time.monotonic()
    try:
        p = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        return {"command": command, "utc": started, "seconds": round(time.monotonic() - tick, 3),
                "exit_code": p.returncode, "stdout": p.stdout, "stderr": p.stderr}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"command": command, "utc": started, "seconds": round(time.monotonic() - tick, 3),
                "exit_code": 124 if isinstance(exc, subprocess.TimeoutExpired) else 127,
                "stdout": "", "stderr": type(exc).__name__}


def docker_forge(command):
    run_id = uuid.uuid4().hex
    name = "t3l4n-contract-check-" + run_id
    args = ["docker", "run", "--rm", "--pull", "never", "--name", name,
            "--label", "com.t3l4n.project=contracts", "--label", "com.t3l4n.check=" + run_id,
            "--platform", "linux/amd64", "--network", "none", "--user", "1000:1000",
            "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
            "--memory", "1g", "--cpus", "2", "--pids-limit", "128",
            "--log-opt", "max-size=5m", "--log-opt", "max-file=2",
            "--tmpfs", "/tmp:rw,nosuid,size=128m", "-v", str(ROOT) + ":/work", "-w", "/work",
            "--entrypoint", "forge", IMAGE, *command]
    result = execute(args)
    if result["exit_code"] == 124:
        inspect = execute(["docker", "inspect", name], timeout=15)
        if inspect["exit_code"] == 0:
            container = json.loads(inspect["stdout"])[0]
            if container["Config"]["Labels"].get("com.t3l4n.check") == run_id:
                result["targeted_cleanup"] = execute(["docker", "rm", "--force", name], timeout=15)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=PROJECT / ".local/contracts-verification.json")
    args = parser.parse_args()
    before = snapshot()
    report = {"schema_version": 1, "utc_start": utc(), "environment": "Foundry in offline Docker, simulated chain IDs",
              "source_files": before, "image": IMAGE, "fuzz_seed": SEED, "commands": [], "passed": False,
              "limits": ["Not a test of two RPC networks or relayer persistence", "No Sepolia or TELA execution", "No performance benchmark", "Conservation invariant excludes external mint/burn and executor fraud"]}
    commit = execute(["git", "rev-parse", "HEAD"], timeout=15)
    report["source_commit"] = commit["stdout"].strip() if commit["exit_code"] == 0 else None
    report["git_status"] = execute(["git", "status", "--porcelain=v1", "--", "contracts"], timeout=15)["stdout"]
    verification = execute([sys.executable, str(ROOT / "tools/prepare.py"), "--offline"])
    report["commands"].append(verification)
    if verification["exit_code"] == 0:
        report["commands"].append(docker_forge(["--version"]))
        report["commands"].append(docker_forge(["build", "--use", "/work/.toolchain/solc-0.8.30", "--sizes"]))
        tests = docker_forge(["test", "--use", "/work/.toolchain/solc-0.8.30", "--fuzz-seed", SEED, "--json"])
        report["commands"].append(tests)
        if tests["exit_code"] == 0:
            try:
                suites = json.loads(tests["stdout"])
                results = [dict(suite=suite, test=name, **test) for suite, data in suites.items()
                           for name, test in data["test_results"].items()]
                report["test_count"] = len(results)
                report["test_results"] = results
                report["passed"] = bool(results) and all(r["status"] == "Success" for r in results)
            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                report["parse_error"] = type(exc).__name__
        try:
            report["artifacts"] = compiled_artifacts()
            if any(a["compiler"] != "0.8.30+commit.73712a01" or a["evm_version"] != "london"
                   or a["optimizer"] != {"enabled": True, "runs": 200} for a in report["artifacts"].values()):
                report["artifact_error"] = "Compiled settings differ from the expected pinned compiler, EVM or optimizer"
                report["passed"] = False
        except (OSError, ValueError, KeyError, TypeError) as exc:
            report["artifact_error"] = type(exc).__name__
            report["passed"] = False
    image = execute(["docker", "image", "inspect", IMAGE, "--format", "{{json .}}"], timeout=15)
    if image["exit_code"] == 0:
        observed = json.loads(image["stdout"])
        report["image_observed"] = {key: observed.get(key) for key in ("Id", "RepoDigests", "Architecture", "Os")}
    else:
        report["image_error"] = image
        report["passed"] = False
    report["source_unchanged"] = before == snapshot()
    report["passed"] = report["passed"] and report["source_unchanged"] and all(c["exit_code"] == 0 for c in report["commands"])
    report["source_sha256"] = sha256(json.dumps(before, sort_keys=True, separators=(",", ":")).encode())
    report["utc_end"] = utc()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "test_count": report.get("test_count", 0),
                      "report": str(args.output), "sha256": sha256(args.output.read_bytes())}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
