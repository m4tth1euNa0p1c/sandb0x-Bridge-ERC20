---
name: bridge-pause
description: "Définir ou tester la pause T3l4N, ses effets sur les opérations en transit et sa levée."
---

# Vérifier pause et reprise métier

**Entrées.** Fonctions pausable, rôles, état du relayer et transferts à différentes étapes.

## Procédure

1. Préciser si la pause bloque demandes source, mint destination, collecte et soumission ; maintenir l'observation utile au diagnostic lorsque cela est prévu.
2. Tester pause avant burn, après burn et après diffusion destination. Une pause ne retire pas une transaction déjà finalisée.
3. Vérifier qu'une reprise n'efface ni identifiants traités ni checkpoints et ne déclenche pas de mint compensatoire pour un timeout antérieur.
4. Exercer les droits distincts de pause et d'administration, puis conserver l'état des transferts restants et les actions d'opérateur nécessaires.

**Livrable.** Matrice d'effets de pause, événements et preuve de reprise idempotente.

**Limite.** Ne lever aucune pause d'un réseau partagé sans autorisation applicable et motif documenté.
