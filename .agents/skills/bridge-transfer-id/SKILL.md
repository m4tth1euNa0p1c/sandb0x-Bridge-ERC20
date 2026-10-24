---
name: bridge-transfer-id
description: "Concevoir ou auditer l'identifiant déterministe T3l4N et les protections contre le rejeu intercontexte."
---

# Définir le domaine des identifiants

**Entrées.** Schéma du protocole, ABI d'événement, calcul on-chain et encodage off-chain.

## Procédure

1. Inclure version du protocole, chaînes et bridges source/destination, paire de tokens, nonce, montant entier et destinataire dans un encodage non ambigu.
2. Préférer un encodage typé explicite ; si des champs dynamiques existent, ne pas concaténer naïvement des valeurs avec abi.encodePacked.
3. Produire des vecteurs partagés entre Solidity et .NET, puis modifier un seul champ de domaine à la fois pour vérifier que l'identifiant change.
4. Tester répétition exacte à destination et rejeu vers un autre bridge, réseau, token ou destinataire ; distinguer id métier, tx hash et clé de log.

**Livrable.** Schéma versionné, vecteurs indépendants et tests de rejeu ciblés.

**Limite.** Ne pas changer l'encodage d'une version déjà déployée sans stratégie explicite de migration de domaine.
