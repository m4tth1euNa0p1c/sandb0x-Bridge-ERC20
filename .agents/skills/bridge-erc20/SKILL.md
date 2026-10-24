---
name: bridge-erc20
description: "Établir la compatibilité d'un token avec le bridge T3l4N avant ajout d'une paire ou usage d'un contrat existant."
---

# Évaluer un token ERC20

**Entrées.** Adresse réseau, ABI, bytecode, decimals et description des rôles du token.

## Procédure

1. Vérifier les fonctions effectives de mint et burn, leurs restrictions et les allowances éventuelles ; ERC20 standard ne garantit aucune de ces permissions.
2. Examiner rebase, frais de transfert, hooks, gel, listes d'accès et possibilité d'émissions externes. Rejeter les comportements non pris en charge par la première version.
3. Comparer les decimals des deux tokens et la représentation entière des montants. Commencer par des tokens de test dédiés avec même précision.
4. Conserver la preuve des droits disponibles ; si le token est incompatible, décrire lock/mint ou adaptation autorisée comme options, sans changer silencieusement son contrat.

**Livrable.** Matrice de compatibilité du token et décision accepter/refuser avec hypothèses.

**Limite.** Ne pas modifier un token existant ou ses administrateurs pour faire passer les tests.
