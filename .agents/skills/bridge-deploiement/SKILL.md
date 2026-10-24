---
name: bridge-deploiement
description: "Préparer ou exécuter un déploiement T3l4N autorisé sur un profil local ou testnet vérifié."
---

# Reproduire un déploiement de test

**Entrées.** Artefacts compilés, configuration réseau validée, signataire dédié et politique d'administration.

## Procédure

1. Vérifier identité du réseau avant signature, compiler avec versions verrouillées et conserver hash du bytecode ainsi que paramètres de constructeur non secrets.
2. Prévoir l'ordre token, bridge, paire et rôles ; vérifier chaque reçu et code déployé avant la transaction suivante dépendante.
3. Conserver adresses, chain ID, hash de bloc, tx hash et état final des rôles. Un script terminé sans erreur n'est pas suffisant si une transaction n'est pas finalisée.
4. Rendre une relance explicite : réutiliser un déploiement vérifié ou créer une nouvelle version documentée, sans redéployer par défaut après timeout.

**Livrable.** Manifeste de déploiement et vérifications on-chain des paramètres finaux.

**Limite.** Aucun mainnet, actif réel ou réseau non confirmé de test ; aucune clé publique Anvil sur réseau partagé.
