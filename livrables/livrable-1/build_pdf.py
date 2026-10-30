#!/usr/bin/env python3
"""Génère le PDF du livrable 1 en deux passes : rendu, relevé des pages des titres, rendu final paginé.

Prérequis : Node.js avec Playwright et Chromium, Python avec pypdf. Aucun accès réseau pendant le rendu.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from pypdf import PdfReader, PdfWriter

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "Livrable-1_Architecture_Bridge_Sepolia-TELA_v1.0.pdf"
METADATA = {
    "/Title": "Bridge ERC20 Sepolia – TELA · Livrable 1 · Document d'architecture",
    "/Author": "Matthieu Barraque",
    "/Subject": "Architecture interne, démonstration, risques, charges et compétences du bridge burn & mint",
    "/Keywords": "TELA, Sepolia, Besu, ERC20, bridge, burn, mint, relayer, architecture",
}


def render(pdf, pages=None):
    args = ["node", str(HERE / "build.mjs"), str(pdf)]
    if pages:
        args.append(str(pages))
    env = dict(os.environ)
    env.setdefault("NODE_PATH", "/opt/node22/lib/node_modules")
    result = subprocess.run(args, cwd=HERE, env=env, capture_output=True, text=True, timeout=300)
    if result.returncode:
        sys.exit("Rendu en échec :\n" + result.stdout + result.stderr)
    return json.loads(result.stdout.strip().splitlines()[-1])


def heading_pages(pdf):
    reader = PdfReader(pdf)
    index = {page.indirect_reference.idnum: number for number, page in enumerate(reader.pages, start=1)}
    pages = {}
    for name, destination in reader.named_destinations.items():
        pages[name.lstrip("/")] = index[destination.page.idnum]
    return pages, len(reader.pages)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(OUTPUT))
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="livrable1-") as work:
        first = Path(work) / "pass1.pdf"
        report = render(first)
        pages, count = heading_pages(first)
        mapping = Path(work) / "pages.json"
        mapping.write_text(json.dumps(pages))
        final = Path(work) / "final.pdf"
        render(final, mapping)
        check, count2 = heading_pages(final)
        if check != pages or count2 != count:
            sys.exit("La pagination a changé entre les deux passes ; vérifier la mise en page du sommaire.")
        writer = PdfWriter(clone_from=str(final))
        # Signets reconstruits : Chromium duplique le texte des titres numérotés.
        del writer.root_object["/Outlines"]
        writer.add_outline_item("Couverture", 0)
        writer.add_outline_item("Fiche document", 1)
        writer.add_outline_item("Sommaire", 2)
        parent = None
        for item in report["outline"]:
            title = (item["num"] + "  " + item["title"]).strip()
            if item["level"] == 1:
                parent = writer.add_outline_item(title, pages[item["id"]] - 1)
            else:
                writer.add_outline_item(title, pages[item["id"]] - 1, parent=parent)
        writer.page_mode = "/UseOutlines"
        writer.add_metadata({**METADATA, "/Creator": "build_pdf.py (Chromium/Playwright, Mermaid 11.16.1)"})
        with open(args.output, "wb") as handle:
            writer.write(handle)
    digest = hashlib.sha256(Path(args.output).read_bytes()).hexdigest()
    print(json.dumps({"pdf": Path(args.output).name, "pages": count, "diagrammes_mermaid": report["diagrams"],
                      "titres": report["headings"], "sha256": digest}, ensure_ascii=False))


if __name__ == "__main__":
    main()
