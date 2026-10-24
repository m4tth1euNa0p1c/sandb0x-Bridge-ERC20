---
name: bridge-anvil
description: "Préparer ou vérifier les deux nœuds Anvil T3l4N pour les expériences de protocole et de panne."
---

# Exercer les chaînes Anvil locales

**Entrées.** Profil local-fast, image Foundry verrouillée et endpoints locaux attendus.

## Procédure

1. Vérifier chain ID, clientVersion et hash genesis de chaque endpoint avant l'expérience ; ne pas accepter deux URLs pointant vers la même chaîne.
2. Fixer hardfork et paramètres de mining utiles au scénario. Les confirmations Anvil sont une convention de test, sans implication sur la finalité TELA.
3. Empêcher l'affichage des clés de développement ; réserver les comptes publics Anvil au réseau local. Ne pas utiliser fork-url sans besoin et autorisation explicites.
4. Lors d'un scénario persistant, distinguer état disque, mémoire et historique RPC réellement conservé ; vérifier après redémarrage au lieu de supposer la persistance.

**Livrable.** Identités des deux chaînes, paramètres et assertions du scénario exécuté.

**Limite.** Ne pas transformer un anvil_mine ou un snapshot/revert en démonstration d'une finalité de réseau partagé.
