---
name: bridge-migrations
description: "Préparer ou tester une migration PostgreSQL T3l4N sans invalider les données de reprise."
---

# Faire évoluer la persistance

**Entrées.** Schéma actuel, données de test représentatives, nouvelle version et plan de récupération.

## Procédure

1. Évaluer l'effet sur clés d'unicité, états existants, nonces réservés et transactions déjà diffusées ; ne pas réinitialiser ces tables pour simplifier l'évolution.
2. Exécuter la migration sur une copie de données de test avec vérification du nombre et de l'identité des lignes avant/après.
3. Définir compatibilité ancien/nouveau worker, fenêtre d'arrêt et rollback possible ; une migration irréversible doit avoir une restauration éprouvée.
4. Après migration, reprendre des transferts à plusieurs étapes et vérifier réconciliation on-chain avant toute nouvelle soumission.

**Livrable.** Migration, préconditions, vérification des données et procédure de récupération testée.

**Limite.** Ne pas appliquer une migration destructive hors du périmètre autorisé ni sur une base dont l'identité est incertaine.
