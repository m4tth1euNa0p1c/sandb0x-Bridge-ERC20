---
name: bridge-concurrence
description: "Implémenter ou tester la prise de travail concurrente T3l4N sans double soumission métier."
---

# Maîtriser les workers concurrents

**Entrées.** Stratégie de verrouillage SQL, leases éventuels et limites de workers.

## Procédure

1. Choisir un mécanisme explicite de claim, par exemple verrou transactionnel ou lease persistant ; préciser expiration, renouvellement et propriétaire.
2. Exercer deux workers sur le même transfert et sur des transferts distincts ; vérifier la visibilité des transactions SQL et l'absence de verrou réseau prolongé inutile.
3. Simuler perte du worker détenteur puis reprise par un autre ; un lease expiré ne rend pas sûre la rediffusion sans réconciliation on-chain.
4. Vérifier que l'allocation de nonce et le claim du transfert restent cohérents sous concurrence, avec contraintes d'unicité comme dernier garde-fou.

**Livrable.** Chronologie des workers, transactions SQL et assertions sur effets et nonces.

**Limite.** Ne pas se contenter d'un lock en mémoire si plusieurs processus ou redémarrages sont possibles.
