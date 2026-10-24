---
name: bridge-decimals
description: "Vérifier conversions et précision des montants ERC20 T3l4N entre interfaces, .NET et contrats."
---

# Préserver les unités entières

**Entrées.** Decimals de la paire, montants d'entrée, ABI et types de persistance.

## Procédure

1. Vérifier les decimals on-chain et leur égalité pour la première version ; refuser les paires non prises en charge avant burn.
2. Utiliser des entiers arbitraires pour les unités de base et une conversion décimale exacte de l'entrée utilisateur ; jamais float ou double.
3. Rejeter une précision supérieure à celle du token au lieu d'arrondir silencieusement ; tester zéro, unité minimale, maximum autorisé et maximum uint256.
4. Conserver dans événements et base le montant en unités de base ; réserver le format humain à l'affichage avec sa précision explicitée.

**Livrable.** Vecteurs de conversion aller-retour et refus des montants ou précisions invalides.

**Limite.** Ne pas appliquer un taux de conversion entre tokens dont les decimals diffèrent sans nouveau modèle validé.
