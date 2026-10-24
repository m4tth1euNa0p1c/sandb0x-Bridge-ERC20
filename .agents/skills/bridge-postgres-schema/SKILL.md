---
name: bridge-postgres-schema
description: "Concevoir ou examiner le schéma PostgreSQL T3l4N des événements, transferts et transactions."
---

# Modéliser les états persistants

**Entrées.** Machine à états, clés de domaine, stratégie de concurrence et exigences de reprise.

## Procédure

1. Distinguer observation de log, transfert métier, tentative de soumission et transaction signée ; plusieurs tentatives ne doivent pas devenir plusieurs transferts.
2. Stocker montants et nonces sans perte entière, hashes avec format contrôlé et timestamps UTC ; définir uniques, foreign keys et transitions valides.
3. Prévoir observed, source_finalized, destination_submitted, destination_finalized ainsi que waiting, retryable_failed, rejected et intervention_required selon le modèle retenu.
4. Séparer compte de migration et droits du relayer ; tester intégrité et accès avec les rôles réels au lieu de valider seulement avec un superutilisateur.

**Livrable.** Schéma versionné, invariants SQL et scénarios de contraintes.

**Limite.** Une base démarrée ou une table témoin persistante ne prouve pas la persistance d'un relayer absent.
