---
name: bridge-reorg
description: "Exercer le traitement T3l4N des blocs remplacés avant finalité sur un environnement permettant une reorg."
---

# Simuler une réorganisation source

**Entrées.** Deux branches locales contrôlées, événement source observé et politique de finalité.

## Procédure

1. Capturer un point avant burn, produire le burn et laisser le collecteur l'observer sans atteindre la finalité définie.
2. Revenir au point contrôlé puis produire une branche concurrente ; vérifier hashes et disparition du log pour démontrer que le scénario est bien une reorg.
3. Vérifier que l'événement orphelin ne devient pas mintable, que le checkpoint se recale et que les observations de branche sont conservées sans confusion.
4. Si une anomalie touche un événement déjà traité à destination, exiger une intervention explicite plutôt qu'un mint ou burn compensatoire automatique.

**Livrable.** Trace des branches, états du transfert et absence d'effet destination dans le scénario préfinalité.

**Limite.** Limiter la conclusion au scénario Anvil exécuté ; cela ne démontre pas la finalité du véritable TELA.
