---
name: bridge-menaces
description: "Analyser le modèle de menace T3l4N lors d'un changement de rôles, de signature ou de frontières de confiance."
---

# Analyser les pouvoirs et les menaces

**Entrées.** Diagramme des composants, pouvoirs des comptes, entrées non fiables et limitations de déploiement.

## Procédure

1. Énumérer les actifs de test et les pouvoirs concrets : mint, pause, attribution de rôles, modification de configuration, accès à la base et au moteur Docker.
2. Pour une clé d'exécution compromise, construire le scénario de mint frauduleux autorisé par contrat ; ne pas assimiler autorisation à preuve du burn.
3. Pour chaque scénario, distinguer prévention, détection, confinement et récupération. Noter les actions irréversibles déjà incluses sur une chaîne.
4. Identifier les contrôles seulement déclarés et ceux effectivement exercés. Un conteneur durci ne confine ni l'opérateur Docker ni Codex sur l'hôte.

**Livrable.** Table menace, précondition, impact, contrôle, preuve et risque résiduel.

**Limite.** N'attribuer aucune protection de quorum, HSM ou preuve cryptographique à un mécanisme seulement envisagé.
