#!/usr/bin/env python3
"""Valide le catalogue local d'agents et de skills, sans appeler un modèle.

Python >= 3.11. Le frontmatter des skills utilise volontairement deux scalaires
YAML (name et description), sans ancres, tags ou blocs multilignes. Cette
convention de projet permet une vérification sans dépendance supplémentaire.
La validation couvre la structure et les associations, pas la qualité des agents.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import sys
import tomllib


MINIMUM = 50
ROOT = Path(__file__).resolve().parents[1]
REQUIRED_AGENT_FIELDS = {"name", "description", "developer_instructions"}
# Aucun rôle ne doit essayer d'élargir ses permissions ni imposer un modèle.
FORBIDDEN_AGENT_FIELDS = {
    "model", "model_provider", "model_reasoning_effort", "model_service_tier",
    "approval_policy", "sandbox_mode", "permissions", "network_access",
    "mcp_servers", "dangerously_bypass_approvals_and_sandbox",
}


class CatalogError(ValueError):
    """Erreur de structure ou de correspondance du catalogue."""


def scalar(value: str) -> str:
    value = value.strip()
    if value.startswith('"'):
        parsed = json.loads(value)
        if not isinstance(parsed, str):
            raise CatalogError("le scalaire cité doit être une chaîne")
        return parsed
    if value.startswith("'"):
        if len(value) < 2 or not value.endswith("'"):
            raise CatalogError("guillemets simples non fermés")
        inner = value[1:-1]
        if "'" in inner.replace("''", ""):
            raise CatalogError("apostrophe YAML non échappée")
        return inner.replace("''", "'")
    if not value or any(char in value for char in ":#{}[]&*!>|\n"):
        raise CatalogError("scalaire YAML non pris en charge ; utiliser une chaîne entre guillemets doubles")
    return value


def parse_skill(path: Path) -> tuple[dict[str, str], str]:
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()
    if not lines or lines[0] != "---":
        raise CatalogError("frontmatter YAML absent")
    try:
        end = lines.index("---", 1)
    except ValueError as exc:
        raise CatalogError("frontmatter YAML non fermé") from exc
    fields: dict[str, str] = {}
    for line in lines[1:end]:
        if not line.strip():
            continue
        key, separator, value = line.partition(":")
        if not separator or key not in {"name", "description"} or key in fields:
            raise CatalogError("champ inconnu, dupliqué ou invalide dans le frontmatter")
        fields[key] = scalar(value)
    if set(fields) != {"name", "description"}:
        raise CatalogError("name et description sont requis")
    name, description = fields["name"], fields["description"]
    if len(name) > 64 or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
        raise CatalogError("nom de skill invalide")
    if not description.strip() or len(description) > 1024 or "<" in description or ">" in description:
        raise CatalogError("description vide, trop longue ou non conforme")
    body = "\n".join(lines[end + 1:]).strip()
    if not body or re.search(r"(?m)^\s*\[TODO:.*\]\s*$", body):
        raise CatalogError("instructions absentes ou échafaudage inachevé")
    return fields, body


def forbidden_keys(value: object, prefix: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else key
            if key in FORBIDDEN_AGENT_FIELDS:
                found.append(path)
            found.extend(forbidden_keys(item, path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(forbidden_keys(item, f"{prefix}[{index}]"))
    return found


def validate(root: Path) -> dict:
    root = root.resolve()
    errors: list[str] = []
    skills: dict[str, dict] = {}
    agents: dict[str, dict] = {}
    skill_descriptions: set[str] = set()
    agent_descriptions: set[str] = set()
    skill_bodies: set[str] = set()
    hashes: dict[str, str] = {}

    def fail(path: Path, message: str):
        errors.append(f"{path.relative_to(root).as_posix()}: {message}")

    skill_files = sorted((root / ".agents/skills").glob("*/SKILL.md"))
    agent_files = sorted((root / ".codex/agents").glob("*.toml"))
    for path in skill_files:
        try:
            if not path.resolve().is_relative_to(root):
                raise CatalogError("le skill sort du dépôt")
            fields, body = parse_skill(path)
            name = fields["name"]
            if path.parent.name != name or not name.startswith("bridge-"):
                raise CatalogError("le dossier doit correspondre au nom bridge-* du skill")
            if name in skills:
                raise CatalogError("nom de skill dupliqué")
            if fields["description"] in skill_descriptions:
                raise CatalogError("description de skill dupliquée")
            # Détecte un copier-coller intégral, sans prétendre mesurer la pertinence.
            if body in skill_bodies:
                raise CatalogError("corps de skill intégralement dupliqué")
            skill_descriptions.add(fields["description"])
            skill_bodies.add(body)
            skills[name] = fields
            hashes[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        except (OSError, ValueError) as exc:
            fail(path, str(exc))

    for path in agent_files:
        try:
            if not path.resolve().is_relative_to(root):
                raise CatalogError("l'agent sort du dépôt")
            with path.open("rb") as stream:
                fields = tomllib.load(stream)
            forbidden = forbidden_keys(fields)
            if forbidden:
                raise CatalogError("paramètres de modèle/permissions interdits : " + ", ".join(forbidden))
            if set(fields) != REQUIRED_AGENT_FIELDS:
                raise CatalogError("champs autorisés : name, description, developer_instructions")
            if any(not isinstance(fields[k], str) or not fields[k].strip() for k in REQUIRED_AGENT_FIELDS):
                raise CatalogError("les trois champs doivent être des chaînes non vides")
            expected_name = path.stem.replace("-", "_")
            if fields["name"] != expected_name or not re.fullmatch(r"bridge_[a-z0-9_]+", fields["name"]):
                raise CatalogError("nom d'agent et fichier incohérents")
            if fields["name"] in agents:
                raise CatalogError("nom d'agent dupliqué")
            if fields["description"] in agent_descriptions:
                raise CatalogError("description d'agent dupliquée")
            skill_name = path.stem
            skill_ref = f".agents/skills/{skill_name}/SKILL.md"
            if skill_name not in skills:
                raise CatalogError("skill associé absent ou invalide")
            if skill_ref not in fields["developer_instructions"]:
                raise CatalogError("référence explicite au skill associé absente")
            agent_descriptions.add(fields["description"])
            agents[fields["name"]] = {"skill": skill_name, "path": path.relative_to(root).as_posix()}
            hashes[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        except (OSError, ValueError) as exc:
            fail(path, str(exc))

    for skill_name in skills:
        if skill_name.replace("-", "_") not in agents:
            errors.append(f"{skill_name}: agent associé absent ou invalide")
    if len(skills) < MINIMUM:
        errors.append(f"Au moins {MINIMUM} skills valides requis ; observé : {len(skills)}")
    if len(agents) < MINIMUM:
        errors.append(f"Au moins {MINIMUM} agents valides requis ; observé : {len(agents)}")
    return {
        "schema_version": 1,
        "utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "scope": "Structure, unicité, associations agent/skill et absence d'override ; pas une évaluation comportementale",
        "minimum": MINIMUM,
        "skill_files": len(skill_files), "valid_skills": len(skills),
        "agent_files": len(agent_files), "valid_agents": len(agents),
        "associations": agents,
        "sha256": hashes,
        "errors": errors,
        "passed": not errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="Racine du catalogue (défaut : dépôt courant)")
    parser.add_argument("--report", type=Path, help="Rapport JSON optionnel, sans secrets")
    args = parser.parse_args()
    report = validate(args.root)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Catalogue : {report['valid_agents']} agents, {report['valid_skills']} skills ; "
          f"validation {'réussie' if report['passed'] else 'en échec'}")
    for error in report["errors"]:
        print(error, file=sys.stderr)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
