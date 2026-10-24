---
name: bridge-checkpoints
description: "Concevoir ou tester les checkpoints T3l4N pour reprendre sans perdre les événements historiques."
---

# Persister les points de reprise

**Entrées.** Curseurs de collecte, transactions SQL et identité des blocs sources.

## Procédure

1. Définir le checkpoint comme borne précisément inclusive ou exclusive, avec chain ID, contrat et version de filtre pour éviter sa réutilisation dans un autre contexte.
2. Persister événements et déplacement du curseur dans la même transaction SQL ; un crash doit rejouer ou conserver toute la fenêtre, jamais seulement son curseur.
3. En reprise, comparer le blockHash mémorisé à la chaîne courante et reculer jusqu'à un point commun borné selon la politique décidée.
4. Tester fenêtre vide, crash avant commit, crash après commit et reprise avec chevauchement ; vérifier le nombre d'événements métier uniques.

**Livrable.** Schéma de curseur, règle de rollback et expérience de reprise sans omission.

**Limite.** Si l'historique nécessaire n'est plus disponible, bloquer avec intervention requise plutôt que sauter la plage.
