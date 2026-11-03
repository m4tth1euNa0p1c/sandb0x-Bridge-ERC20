# Revue de l'agentic factory — préparation client

État observé le 3 novembre 2026 sur la branche `codex/agentic-factory-clean`, issue de `2fc15a44bc965e7870e56dfa604b3a99bc3be5a2`. Cette revue est ciblée : elle ne certifie ni la qualité comportementale de chaque rôle ni une autonomie complète.

## Ce qui existe

- `.codex/agents/` : 50 définitions de rôles spécialisés, associées à des périmètres et livrables ; exemple : `bridge-architecture.toml`.
- `.agents/skills/` : 50 procédures associées ; exemple : `bridge-architecture/SKILL.md`.
- `docs/agents.md` : catalogue et règles de coordination ; il précise que les définitions ne sont pas 50 processus actifs et que leur chargement dépend de la session.
- `scripts/validate_capabilities.py` : vérification des fichiers, associations et contraintes de structure ; il n'appelle pas de modèle et ne démontre pas l'efficacité des agents.
- `AGENTS.md` : règles de projet, limites de sécurité et exigence actuelle de conserver au moins 50 rôles et 50 skills.
- `docs/claims.yaml`, `evidence/` et `docs/resultats.md` : traçabilité du bridge, dont les campagnes historiques doivent rester associées à leur commit.

Vérification exécutée : `python scripts/validate_capabilities.py` ; code 0, « Catalogue : 50 agents, 50 skills ; validation réussie ». Cette vérification est structurelle. L'exécution de sous-agents dans cette session, leur qualité, leur coût et leur temps de traitement n'ont pas été mesurés.

## À conserver

| Élément | Utilité | Décision proposée |
|---|---|---|
| `AGENTS.md` | Objectifs, limites, sécurité et conservation des preuves | Garder ; réviser seulement après accord sur le périmètre du produit. |
| Catalogue agents et skills | Procédures spécialisées sur le bridge | Garder en l'état pendant la revue ; sélectionner à l'usage au lieu de tous les activer. |
| Validateur et ses tests | Détecter les ruptures de structure et d'association | Garder ; sa réussite ne prouve pas la performance des agents. |
| Exigences, ADR et preuves | Relier décisions, code et expériences | Garder ; éviter de présenter une preuve historique comme actuelle. |
| Code, tests et infrastructure du bridge | Sujet métier concret de la démonstration | Garder pour une démonstration liée au bridge ; une extraction générique exige une décision produit distincte. |

## À examiner ensemble avant suppression

1. **Granularité des 50 paires** : certains sujets voisins pourraient être regroupés, notamment collecte/checkpoints/déduplication et métriques/alertes/Grafana. C'est une hypothèse de simplification, pas une duplication démontrée. Comparer missions, déclencheurs et résultats avant toute fusion.
2. **Contraintes de décompte** : `AGENTS.md` et `scripts/validate_capabilities.py` imposent 50 paires. Réduire le catalogue suppose une modification explicite de cette exigence et des tests associés ; une simple suppression casserait le contrat actuel.
3. **Spécificité métier** : les rôles dépendent du contexte T3l4N. Une factory réutilisable pour d'autres clients nécessite de séparer les consignes génériques des profils métier et de tester cette séparation.
4. **Preuves historiques** : ne pas supprimer les campagnes simplement pour raccourcir la présentation ; identifier d'abord leurs références et exigences de conservation.
5. **Démonstration** : ne pas exposer des identifiants, données privées ou configurations locales. Vérifier les fichiers montrés avant partage.

## Parcours de présentation proposé

1. Partir d'une demande concrète : examiner une modification de frontière de confiance du bridge.
2. Montrer `AGENTS.md`, puis le rôle `bridge_architecture` et son skill ; expliquer l'attribution explicite des fichiers et le résultat attendu.
3. Présenter une revue de sécurité et une validation séparées si les capacités de la session sont disponibles ; sinon, expliquer le processus sans simuler d'exécution.
4. Lancer `python scripts/validate_capabilities.py` et expliquer sa portée structurelle.
5. Montrer un livrable vérifiable et ses preuves ; distinguer un résultat historique du commit courant.

**Message exact au client :** il s'agit d'un catalogue spécialisé et de procédures de travail pour Codex, avec validation structurelle et traçabilité. Ce dépôt ne démontre pas à lui seul une usine autonome universelle, un contrôle d'accès indépendant pour chaque rôle, ni une qualité garantie par le nombre de rôles.

## Prochaines décisions

- Choisir si le livrable est une factory spécialisée bridge ou un socle générique accompagné d'un profil bridge.
- Définir un petit jeu de missions représentatives et un protocole de comparaison avant/après : résultat attendu, erreurs, temps et coût mesurés, limites et cas négatifs.
- Examiner les paires candidates à la fusion, puis ajuster exigences et validateur si une réduction est décidée.
- Vérifier le chargement effectif des rôles et réaliser une démonstration en direct dans l'environnement client autorisé.

Aucun fichier existant n'a été supprimé dans cette revue. Le rapport précédent `docs/audits/INDEPENDENT_PROJECT_ASSESSMENT.md` reste préliminaire.
