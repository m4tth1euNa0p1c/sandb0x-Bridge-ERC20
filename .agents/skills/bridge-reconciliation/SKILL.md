---
name: bridge-reconciliation
description: "Construire ou vérifier le contrôle T3l4N de l'offre totale et des transferts encore en transit."
---

# Réconcilier l'offre entre chaînes

**Entrées.** Offre de référence, points de contrôle cohérents sur deux chaînes, burns, mints et émissions externes.

## Procédure

1. Définir S_A + S_B + burns_en_transit = offre_reference, avec ajustement explicite des émissions/destructions externes autorisées et de leur période.
2. Pour chaque direction, compter un burn en transit une seule fois tant que son mint n'est pas inclus au point destination choisi ; la base seule n'est pas un oracle d'offre.
3. Aligner les points de contrôle et la population de transferts pour éviter de compter à la fois un mint déjà inclus et son burn encore marqué en transit.
4. Tester aller/retour simultanés, retard de base, double réception et émission externe ; conserver blocs, hashes, unités et hypothèses.

**Livrable.** Rapport de réconciliation reproductible, écart entier et causes examinées.

**Limite.** En cas de checkpoint incohérent, produire inconclusif plutôt qu'un écart présenté comme fraude ou qu'une réparation automatique.
