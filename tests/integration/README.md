# Tests d'intégration locaux

`python scripts/bridge.py prove --profile local-fast` exécute le transfert
aller-retour, les neuf injections de `tests/resilience.py`, la persistance,
le cloisonnement et la supervision. Le profil `local-besu` exécute sept de ces
injections ; gas nul et réorganisation Anvil y restent non exécutés.

Les doubles RPC .NET vérifient séparément réponses perdues, incohérences et délais.
Le test `observability/tests/stale.py` arrête le relayer du profil choisi,
vérifie les données anciennes puis le redémarre. Les preuves figées et leurs
limites sont dans `docs/resultats.md` et `docs/claims.yaml` ; aucun résultat local
ne valide Sepolia ou TELA. La matrice attendue figure dans `docs/tests-preuves.md`.
