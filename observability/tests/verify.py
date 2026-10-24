"""Vérifications Prometheus reproductibles, exécutées dans l'image verrouillée."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=Path(".local/monitoring-checks.json"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    image = json.loads((root / "sandbox/versions.lock.json").read_text(encoding="utf-8"))["images"]["prometheus"]
    base = [
        "docker", "run", "--rm", "--pull", "never", "--network", "none", "--read-only", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges:true", "--pids-limit", "64", "--memory", "256m",
        "--cpus", "1", "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m,mode=1777",
        "--mount", f"type=bind,source={root / 'observability'},target=/work,readonly",
        "--workdir", "/work/tests", "--entrypoint", "/bin/promtool", image,
    ]
    commands = [
        [*base, "--version"],
        [*base, "check", "config", "/work/prometheus/prometheus.yml"],
        [*base, "test", "rules", "/work/tests/rules.test.yml"],
    ]
    results = []
    for command in commands:
        completed = subprocess.run(command, cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        results.append({"command": command, "exit_code": completed.returncode,
                        "stdout": completed.stdout, "stderr": completed.stderr})
        print(completed.stdout, end="")
        if completed.stderr:
            print(completed.stderr, file=sys.stderr, end="")
    dashboard = json.loads((root / "observability/grafana/dashboards/bridge.json").read_text(encoding="utf-8"))
    assert dashboard["uid"] == "t3l4n-bridge"
    assert dashboard["timezone"] == "utc" and dashboard["refresh"] == "5s"
    assert len({panel["id"] for panel in dashboard["panels"]}) == len(dashboard["panels"])
    assert all(panel["fieldConfig"]["defaults"]["noValue"] == "Indisponible"
               for panel in dashboard["panels"] if panel["type"] != "text")
    paths = sorted(path for path in (root / "observability").rglob("*") if path.is_file() and "__pycache__" not in path.parts)
    paths += [root / "sandbox/compose.monitoring.yaml", root / "sandbox/versions.lock.json"]
    source_hashes = {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    git_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
    git_status = subprocess.run(["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True, check=True).stdout.splitlines()
    report = {
        "utc": dt.datetime.now(dt.timezone.utc).isoformat(), "source_commit": git_commit,
        "git_status": git_status, "source_sha256": source_hashes, "image": image,
        "commands": results, "dashboard_static_checks": "passed",
        "scope": "Syntaxe configuration, scénarios de règles promtool et structure JSON du dashboard. Aucun rendu visuel ni connexion au relayer n'est prouvé par cette commande.",
        "passed": all(item["exit_code"] == 0 for item in results),
    }
    report_path = args.report if args.report.is_absolute() else root / args.report
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Rapport : {report_path}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
