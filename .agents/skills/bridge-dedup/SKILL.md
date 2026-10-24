---
name: bridge-dedup
description: "Implémenter ou vérifier les clés d'unicité T3l4N face aux logs répétés et reprises de workers."
---

# Garantir la déduplication métier

**Entrées.** Identifiant de transfert, identité de log, schéma SQL et mapping processed destination.

## Procédure

1. Séparer clé d'observation du log et clé métier du transfert ; conserver les versions de branche nécessaires aux réorganisations.
2. Poser les contraintes d'unicité SQL correspondant aux identités choisies et traiter un conflit comme une observation à réconcilier, pas comme une permission de mint.
3. Tester plusieurs réceptions du même log, rescans chevauchants et deux workers concurrents ; constater un seul effet métier destination.
4. Vérifier on-chain le rejet d'un identifiant déjà consommé même si la base est perdue ou la demande relancée par un autre processus.

**Livrable.** Contraintes et tests de répétition à la collecte, en base et à destination.

**Limite.** Ne pas promettre exactly-once de bout en bout : viser traitement réessayable avec effet métier idempotent.
