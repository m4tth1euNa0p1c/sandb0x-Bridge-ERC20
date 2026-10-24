"""Construit et vérifie les diagrammes MkDocs avec un navigateur local sans HTTP externe."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
from html.parser import HTMLParser
import http.server
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import threading
import uuid


class HtmlObservation(HTMLParser):
    def __init__(self):
        super().__init__()
        self.html = {}
        self.remote_resources = []
        self.svg_count = 0
        self.graphic_count = 0
        self.rendered = 0

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "html":
            self.html = values
        if tag in ("script", "img", "iframe", "source"):
            self.inspect_resource(values.get("src", ""))
        if tag == "link" and values.get("rel") in ("stylesheet", "preload", "modulepreload"):
            self.inspect_resource(values.get("href", ""))
        self.svg_count += tag == "svg"
        self.graphic_count += tag in ("path", "rect", "polygon")
        self.rendered += values.get("data-mermaid-result") == "rendered"

    def inspect_resource(self, value):
        if value.startswith(("http://", "https://", "//")):
            self.remote_resources.append(value)


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    build_python = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    output = root / ".local/mermaid-validation" / dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output.mkdir(parents=True, exist_ok=False)
    site = output / "site"
    report = {"utc": dt.datetime.now(dt.timezone.utc).isoformat(), "commands": [], "pages": [], "passed": False}

    def source_hashes():
        paths = [root / "mkdocs.yml", root / "tests/docs_mermaid.py", *sorted((root / "docs").rglob("*"))]
        return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}

    tested_sources = source_hashes()

    def execute(command, timeout=90):
        result = subprocess.run(command, cwd=root, capture_output=True, timeout=timeout,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        report["commands"].append({"command": [str(x) for x in command], "exit_code": result.returncode,
                                   "stderr": result.stderr.decode("utf-8", errors="replace")[-10000:]})
        assert result.returncode == 0, "Échec de commande ; consulter le rapport"
        return result.stdout

    server = None
    try:
        vendor = root / "docs/assets/vendor/mermaid-11.16.1"
        provenance = json.loads((vendor / "upstream.json").read_text(encoding="utf-8"))
        for name, expected in provenance["files"].items():
            assert hashlib.sha256((vendor / name).read_bytes()).hexdigest() == expected["sha256"], "Empreinte fournisseur différente"
        report["vendor"] = provenance
        assert build_python.is_file(), "Environnement .venv absent : exécuter le bootstrap du dépôt"
        execute([str(build_python), "-m", "mkdocs", "build", "--strict", "--site-dir", str(site)])
        for html in site.rglob("*.html"):
            parsed = HtmlObservation()
            parsed.feed(html.read_text(encoding="utf-8"))
            assert not parsed.remote_resources, f"Ressource HTTP distante dans {html.relative_to(site)}"
        report["html_external_resources"] = 0
        candidates = [args.browser] if args.browser else [
            Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
            Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
            *(Path(p) for name in ("chromium", "chromium-browser", "google-chrome") if (p := shutil.which(name))),
        ]
        browser = next((p for p in candidates if p and p.is_file()), None)
        assert browser, "Chrome/Chromium/Edge absent : rendu navigateur non exécuté"
        with socket.socket() as probe:
            probe.settimeout(.5)
            assert probe.connect_ex(("127.0.0.1", 9)) != 0, "Le port de proxy fermé attendu est occupé"
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), lambda *a, **kw: QuietHandler(*a, directory=str(site), **kw))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{server.server_port}"
        # Ce témoin prouve que la session navigateur refuse l'accès HTTP externe.
        (site / "offline-canary.html").write_text("<html><body><script>document.documentElement.dataset.browser=navigator.userAgent;fetch('https://example.com/bridge-offline-canary').then(()=>document.documentElement.dataset.external='reachable').catch(()=>document.documentElement.dataset.external='blocked');</script></body></html>", encoding="utf-8")
        pages = [("offline-canary.html", 0), ("architecture/index.html", 2), ("adr/0003-reprise-finalite/index.html", 1)]
        for index, (page, expected) in enumerate(pages):
            profile = output / ("browser-" + uuid.uuid4().hex)
            command = [str(browser), "--headless=new", "--disable-gpu", "--disable-background-networking",
                       "--disable-sync", "--disable-extensions", "--disable-default-apps", "--disable-component-update",
                       "--no-first-run", "--no-default-browser-check", "--disable-quic", "--hide-scrollbars",
                       "--proxy-server=http://127.0.0.1:9", "--proxy-bypass-list=127.0.0.1",
                       "--virtual-time-budget=5000",
                       "--window-size=1440,1800", f"--user-data-dir={profile}", "--dump-dom",
                       f"--screenshot={output / ('page-' + str(index) + '.png')}", base + "/" + page]
            dom = execute(command)
            (output / f"page-{index}.html").write_bytes(dom)
            parsed = HtmlObservation()
            parsed.feed(dom.decode("utf-8", errors="replace"))
            observation = {"path": page, "expected_diagrams": expected, "rendered": parsed.rendered,
                           "svg_count": parsed.svg_count, "graphic_count": parsed.graphic_count, "attributes": parsed.html}
            report["pages"].append(observation)
            if expected == 0:
                assert parsed.html.get("data-external") == "blocked", "Le témoin HTTP externe n'a pas été refusé"
                report["browser_user_agent"] = parsed.html.get("data-browser")
            else:
                assert parsed.html.get("data-mermaid-ready") == "true", "Rendu Mermaid incomplet"
                assert parsed.html.get("data-mermaid-errors") == "0", "Erreur de diagramme"
                assert parsed.rendered == expected and parsed.svg_count >= expected and parsed.graphic_count > expected
            assert (output / f"page-{index}.png").is_file(), "Capture navigateur absente"
        assert source_hashes() == tested_sources, "Sources modifiées pendant le test : relancer sur une version stable"
        report["passed"] = True
    except Exception as error:
        report["error"] = f"{type(error).__name__}: {error}"
    finally:
        if server:
            server.shutdown()
            server.server_close()
    report["source_commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    report["git_status"] = subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True).splitlines()
    report["source_sha256"] = tested_sources
    report["sources_unchanged_at_end"] = source_hashes() == tested_sources
    report["artefact_sha256"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.glob("page-*.*")}
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "report": str(output / "report.json"), "error": report.get("error")}, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
