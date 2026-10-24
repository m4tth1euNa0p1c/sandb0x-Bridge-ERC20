---
name: bridge-rpc-pannes
description: "Construire des scénarios T3l4N de RPC indisponible, lent ou incohérent avec assertions sur l'état métier."
---

# Exercer les pannes RPC

**Entrées.** Client RPC, timeout configuré, injection contrôlée et opérations sans actif réel.

## Procédure

1. Séparer connexion refusée, latence au-delà du timeout, réponse JSON invalide, erreur JSON-RPC et réponse sémantiquement contradictoire.
2. Observer checkpoints et transitions : une collecte en erreur ne doit pas avancer le curseur ; un envoi ambigu exige réconciliation.
3. Tester restauration du RPC et rattrapage historique, en gardant les bornes de tentatives et l'ancienneté des opérations en attente.
4. Vérifier logs corrélés sans URL authentifiée, métriques à cardinalité bornée et état de santé dégradé.

**Livrable.** Scénarios exécutés, réponses injectées et assertions d'absence de perte ou de double effet.

**Limite.** Ne pas mettre en panne un endpoint partagé non autorisé ; utiliser un proxy ou client de test contrôlé.
