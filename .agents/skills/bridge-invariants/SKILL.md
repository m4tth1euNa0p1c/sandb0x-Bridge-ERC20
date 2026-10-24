---
name: bridge-invariants
description: "Concevoir des tests stateful Foundry T3l4N sur des séquences de transferts, rôles et pauses."
---

# Tester les invariants de protocole

**Entrées.** Contrats, actions possibles, modèle d'offre et politique des émissions de test.

## Procédure

1. Construire un handler dont les actions couvrent les transitions réellement autorisées, avec plusieurs acteurs et deux directions lorsque le harness le permet.
2. Tenir des variables fantômes indépendantes pour burns, mints et traitements ; ne pas utiliser uniquement l'état que l'on cherche à vérifier comme oracle.
3. Contrôler conservation sous hypothèses explicites, unicité des effets et maintien des interdictions après pause ou révocation de rôle.
4. Mesurer les compteurs d'actions réussies et de reverts afin d'éviter un invariant qui passe parce que toutes les transactions échouent.

**Livrable.** Invariants, portée du modèle, couverture d'actions et traces de violation éventuelles.

**Limite.** Ne pas présenter un invariant local de harness comme preuve de coordination atomique entre PostgreSQL et deux réseaux.
