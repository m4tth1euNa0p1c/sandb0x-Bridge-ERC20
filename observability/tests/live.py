"""Contrôles HTTP en lecture sur une supervision locale déjà démarrée."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import sys
import urllib.parse
import urllib.request


def request(base: str, path: str, payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(base + path, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.load(response)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=["local-fast", "local-besu"], default="local-fast")
    parser.add_argument("--report", type=Path, default=Path(".local/monitoring-live.json"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    ports = {"local-fast": (18090, 13000), "local-besu": (18091, 13001)}[args.profile]
    prom, graf = f"http://127.0.0.1:{ports[0]}", f"http://127.0.0.1:{ports[1]}"
    report = {"utc": dt.datetime.now(dt.timezone.utc).isoformat(), "profile": args.profile,
              "prometheus": prom, "grafana": graf, "checks": [], "passed": False}
    try:
        health = request(graf, "/api/health")
        assert health["database"] == "ok", "Base interne Grafana indisponible"
        report["checks"].append({"grafana_health": health})
        expected = json.loads((root / "observability/grafana/dashboards/bridge.json").read_text(encoding="utf-8"))
        actual = request(graf, "/api/dashboards/uid/t3l4n-bridge")["dashboard"]
        assert actual["uid"] == expected["uid"]
        actual_expr = [target["expr"] for panel in actual["panels"] for target in panel.get("targets", [])]
        expected_expr = [target["expr"] for panel in expected["panels"] for target in panel.get("targets", [])]
        assert actual_expr == expected_expr, "Dashboard servi différent du fichier attendu"
        report["checks"].append({"dashboard_uid": actual["uid"], "panel_count": len(actual["panels"]),
                                  "file_sha256": hashlib.sha256((root / "observability/grafana/dashboards/bridge.json").read_bytes()).hexdigest()})
        for expr in expected_expr:
            result = request(prom, "/api/v1/query?" + urllib.parse.urlencode({"query": expr}))
            assert result["status"] == "success", "Requête de panneau refusée"
            report["checks"].append({"query": expr, "status": result["status"], "result_count": len(result["data"]["result"])})
        query = request(graf, "/api/ds/query", {"queries": [{"refId": "A", "expr": 'up{job="bridge"}',
                        "datasource": {"uid": "t3l4n-prometheus", "type": "prometheus"}, "instant": True,
                        "range": False, "format": "time_series", "intervalMs": 5000, "maxDataPoints": 100}],
                        "from": "now-1m", "to": "now"})
        assert query["results"]["A"].get("status", 200) == 200 and query["results"]["A"].get("frames"), "Datasource Grafana sans résultat"
        assert not query["results"]["A"].get("error"), "Erreur datasource Grafana"
        report["checks"].append({"grafana_datasource_query": "passed"})
        for expr in ['up{job="bridge"}', "bridge:telemetry_fresh", "bridge_ready"]:
            result = request(prom, "/api/v1/query?" + urllib.parse.urlencode({"query": expr}))["data"]["result"]
            assert len(result) == 1 and float(result[0]["value"][1]) == 1, f"État non nominal : {expr}"
        code = request(prom, "/api/v1/query?query=bridge_code_info")["data"]["result"]
        assert len(code) == 1 and code[0]["metric"]["profile"] == args.profile
        networks = request(prom, "/api/v1/query?query=bridge_network_info")["data"]["result"]
        ids = {item["metric"]["chain_id"] for item in networks}
        assert ids == ({"31337", "31338"} if args.profile == "local-fast" else {"31339", "31340"})
        report["checks"].append({"code": code, "networks": networks})
        report["passed"] = True
    except Exception as error:
        report["error"] = f"{type(error).__name__}: {error}"
    path = args.report if args.report.is_absolute() else root / args.report
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "report": str(path), "error": report.get("error")}, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
