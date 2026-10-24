---
name: bridge-nonces
description: "Implémenter ou auditer la gestion persistante des nonces T3l4N par chaîne et compte signataire."
---

# Réserver les nonces de transaction

**Entrées.** Comptes de test, état latest/pending, transactions persistées et politique de remplacement.

## Procédure

1. Indexer la réservation par chain ID et adresse signataire ; allouer sous protection transactionnelle avec une unicité en base.
2. Réconcilier au démarrage les nonces persistés, les transactions connues et les comptes latest/pending sans écraser une réservation simplement parce qu'un RPC l'ignore.
3. Conserver les transactions remplacées avec le même nonce et leurs hashes ; distinguer remplacement d'une tentative et création d'un nouveau transfert.
4. Tester trous, nonce too low, tx déjà connue et deux workers en concurrence ; vérifier quels cas sont réessayables et lesquels exigent intervention.

**Livrable.** Registre des réservations et tests de réconciliation des séquences.

**Limite.** Ne pas sauter arbitrairement un nonce ni signer un second effet métier pour résoudre un timeout.
