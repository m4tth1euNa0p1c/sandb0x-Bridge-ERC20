---
name: bridge-registre-preuves
description: "Ajouter ou revoir une affirmation T3l4N dans le registre exploitable automatiquement."
---

# Maintenir les affirmations techniques

**Entrées.** Formulation précise, périmètre, hypothèses, code et procédure de vérification.

## Procédure

1. Attribuer un identifiant stable et un statut parmi proposé, implémenté, vérifié_local, vérifié_besu_local, vérifié_sepolia, vérifié_tela, bloqué ou obsolète.
2. Relier attendu et observé au même environnement et à la même version ; une observation de startup ne prouve pas le transfert ou la reprise.
3. Vérifier présence du test exécuté et de son résultat dans le manifeste ; refus, skip et absence d'exécution ne sont pas des validations.
4. Lors d'un changement pertinent, invalider la preuve précédente ou produire une nouvelle campagne ; conserver l'historique des conclusions dépassées.

**Livrable.** Entrée de registre complète et cohérente avec artefacts et version.

**Limite.** Refuser une promotion de statut si la preuve manque, ne couvre pas l'affirmation ou se rapporte à d'autres sources.
