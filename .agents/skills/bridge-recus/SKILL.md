---
name: bridge-recus
description: "Implémenter ou tester la confirmation T3l4N d'un transfert après soumission destination."
---

# Vérifier reçus et état destination

**Entrées.** Hash de transaction persisté, contrat attendu et politique de finalité destination.

## Procédure

1. Vérifier présence du reçu, status, blockHash et canonicalité ; un hash de transaction seul ne prouve ni inclusion ni succès.
2. Décoder les événements du contrat attendu et comparer destinataire, token, montant et transfert. Ne pas accepter un événement homonyme d'une autre adresse.
3. Lire l'état processed et les effets pertinents au point de contrôle choisi ; attendre la condition de finalité avant destination_finalized.
4. Traiter reçu disparu, revert ou divergence reçu/état comme états distincts avec preuves et action de reprise adaptée.

**Livrable.** Décision finalisée ou non, reçus et lectures on-chain corrélés.

**Limite.** Ne pas marquer finalisé sur une réponse RPC null ou sur status réussi sans contrôle du contexte.
