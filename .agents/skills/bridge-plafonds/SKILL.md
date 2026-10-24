---
name: bridge-plafonds
description: "Implémenter ou vérifier les limites de montant, gas, fréquence et tentatives du bridge T3l4N."
---

# Borner montants et coûts de transaction

**Entrées.** Paramètres proposés, unités, comportement du contrat et politique du relayer/signataire.

## Procédure

1. Distinguer limite par transfert, cumul par fenêtre et offre totale autorisée ; préciser l'horloge ou le numéro de bloc qui définit une fenêtre.
2. Appliquer les limites pertinentes au contrat et au signataire plutôt que seulement à l'interface utilisateur ; tester un contournement par appel direct.
3. Tester juste sous, exactement à et au-dessus de chaque seuil, ainsi que débordement, reset de fenêtre et concurrence de deux demandes.
4. Exprimer gas limit, gas price et montant en unités entières séparées ; un budget de gas ne limite pas directement le nombre de tokens créés.

**Livrable.** Paramètres explicites, lieux d'application et tests aux frontières.

**Limite.** Une valeur déclarée mais non lue par le code reste proposée et ne doit pas être présentée comme contrôle actif.
