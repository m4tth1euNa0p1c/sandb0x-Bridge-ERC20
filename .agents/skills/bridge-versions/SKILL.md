---
name: bridge-versions
description: "Réviser le verrouillage T3l4N lorsqu'une dépendance, un compilateur ou une image doit être introduit ou mis à jour."
---

# Verrouiller les versions compatibles

**Entrées.** sandbox/versions.lock.json, global.json, contracts/foundry.toml et notes officielles de versions.

## Procédure

1. Établir la matrice runtime, client EVM, cible du compilateur et bibliothèque. Comparer la cible EVM explicitement configurée aux forks activés dans le genesis Besu testé.
2. Choisir une version pour une raison documentée : support LTS, correction nécessaire ou compatibilité démontrée. Distinguer version candidate et dépendance réellement installée.
3. Résoudre tags en empreintes d'images et verrouiller les dépendances transitives par le mécanisme du gestionnaire. Conserver plateforme et identifiant d'image exécutée.
4. Rejouer les tests concernés par le changement et rendre obsolètes les preuves antérieures ; un pin précis n'est pas une attestation d'absence de vulnérabilité.

**Livrable.** Diff des verrous, justification de version et nouvelle campagne de compatibilité.

**Limite.** Ne pas annoncer un SDK utilisable si le runtime installé diffère du global.json sans roll-forward autorisé.
