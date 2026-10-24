---
name: bridge-roles
description: "Implémenter ou examiner l'administration, la pause et l'exécution des contrats T3l4N."
---

# Séparer les rôles contractuels

**Entrées.** Graphe des rôles, fonctions privilégiées et comptes de test affectés.

## Procédure

1. Construire la matrice fonction → rôle requis → administrateur du rôle. Vérifier aussi les fonctions indirectes qui attribuent des droits de mint.
2. Tester refus sans rôle, attribution et retrait, y compris les appels après révocation ; vérifier les événements de changement de rôle.
3. Éviter que l'exécutant puisse s'octroyer l'administration par une relation de rôles circulaire ou un initialiseur réexécutable.
4. Documenter qui peut nommer un nouveau pauser ou relayer, les délais éventuels et la procédure en cas de perte d'administration.

**Livrable.** Graphe d'autorité et assertions effectives sur les contrôles d'accès.

**Limite.** Ne pas assimiler séparation de rôles logiques à séparation des personnes si la même clé détient plusieurs rôles.
