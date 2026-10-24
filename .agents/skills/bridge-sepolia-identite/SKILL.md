---
name: bridge-sepolia-identite
description: "Vérifier l'identité et les prérequis Sepolia T3l4N avant une expérience d'intégration réelle."
---

# Vérifier l'environnement Sepolia

**Entrées.** RPC autorisé, identité de référence, comptes dédiés de test et adresses de contrats attendues.

## Procédure

1. Vérifier chain ID et genesis de référence ; confirmer les contrats attendus par adresse, code et paramètres. Ne pas traiter le nom commercial du fournisseur comme identité réseau.
2. Interroger les tags de finalité requis avant d'envoyer une transaction. Une réponse latest ne remplace pas silencieusement finalized.
3. Mesurer le solde de gas des comptes de test sans exposer leurs clés. Documenter séparément l'origine du gas et celle des tokens ERC20.
4. Confirmer l'absence de clés publiques Anvil et la limitation des montants, gas et fréquence pour cette campagne précise.

**Livrable.** Rapport d'identité Sepolia et liste des prérequis vérifiés ou bloqués.

**Limite.** Aucune transaction si les identités divergent, si le compte n'est pas dédié ou si les fonds de test manquent.
