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
5. Après un arrêt 137, vérifier `State.OOMKilled` et les limites effectives : le code de sortie seul ne prouve pas un OOM. Conserver l'instantané hors Git avec empreinte et validité JSON avant relance ; une écriture interrompue peut le tronquer.
6. Mesurer le repos séparément de la charge. Sans timer, les helpers du laboratoire avancent les confirmations de façon bornée ; un RPC direct ne les produit pas automatiquement. Ne pas purger transactions/reçus pour réduire la mémoire sans vérifier la réconciliation.
7. Une ancienne lecture historique absente reste un échec explicite. Toute reprise sur copies doit comparer reçus, observations canoniques, nonces et offre ; ne pas déplacer un checkpoint pour masquer une lacune. La fenêtre de réorganisation 128 nécessite 129 en-têtes avec son ancêtre.

**Livrable.** Identités des deux chaînes, paramètres et assertions du scénario exécuté.

**Limite.** Ne pas transformer un anvil_mine ou un snapshot/revert en démonstration d'une finalité de réseau partagé.
