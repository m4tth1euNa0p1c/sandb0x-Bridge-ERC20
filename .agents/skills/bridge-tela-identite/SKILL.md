---
name: bridge-tela-identite
description: "Recueillir et vérifier les prérequis du véritable environnement TELA avant toute activation d'intégration."
---

# Établir l'identité du TELA de test

**Entrées.** docs/informations-manquantes.md, paramètres fournis par l'équipe TELA et autorisation d'environnement de test.

## Procédure

1. Obtenir chain ID et identité de référence, genesis attendu, RPC HTTP et WebSocket éventuel, contraintes VPN, certificats et authentification.
2. Demander version Besu, consensus, forks EVM, disponibilité des informations de finalité, droits de déploiement et mécanisme de gas de test.
3. Comparer les réponses RPC aux références indépendantes fournies ; un chain ID seul n'authentifie pas un réseau. Ne pas enregistrer URL contenant un secret.
4. Inventorier token, ABI, decimals et permissions burn/mint ; conserver les confirmations obtenues et les inconnues, sans modifier de rôle existant.

**Livrable.** Fiche réseau TELA de test sourcée et résultat explicite de chaque contrôle préalable.

**Limite.** Garder l'intégration désactivée si une identité, une permission ou la confirmation test manque.
