---
name: bridge-metriques
description: "Implémenter ou revoir les métriques Prometheus T3l4N du relayer et de la réconciliation."
---

# Instrumenter des métriques bornées

**Entrées.** Événements de la machine à états, politique de labels et vues d'exploitation attendues.

## Procédure

1. Exposer santé, dernière collecte réussie, retard par rapport aux blocs finalisés, transferts en attente/ancienneté, erreurs, tentatives, gas et pause lorsque le code les fournit.
2. Choisir labels bornés tels que profil, chaîne, état et classe d'erreur ; réserver transfer_id, hash et adresse arbitraire aux logs.
3. Distinguer absence de série, valeur zéro et dernière valeur ancienne. Documenter compteurs réinitialisés au redémarrage et gauges dérivées de la base.
4. Vérifier chaque métrique par une expérience observable, puis contrôler exposition et accès réseau du endpoint.

**Livrable.** Catalogue de séries avec unités, labels, sens et expérience de validation.

**Limite.** Ne pas exposer une valeur fictive de gas, de pause ou de réconciliation lorsque le composant n'est pas implémenté.
