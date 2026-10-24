---
name: bridge-finalite
description: "Définir ou vérifier la condition de traitement T3l4N entre inclusion, confirmations et finalisation."
---

# Définir une politique de finalité

**Entrées.** Identité du réseau, APIs RPC disponibles, politique par profil et code de gating.

## Procédure

1. Distinguer block latest, profondeur de confirmations et tag finalized ; écrire la condition exacte autorisant une soumission destination.
2. Tester les méthodes nécessaires contre le RPC réel et enregistrer leurs réponses. Une absence de tag doit provoquer refus ou alternative explicitement décidée.
3. Recontrôler que le hash du bloc source fait partie de la chaîne canonique au moment où le transfert devient éligible.
4. Pour QBFT local, préciser nombre de validateurs et hypothèses ; pour Anvil, nommer la convention de confirmations sans l'exporter à TELA.

**Livrable.** Politique par réseau, test de capacité RPC et assertions du passage source_finalized.

**Limite.** Aucun repli silencieux de finalized vers latest ou vers un nombre arbitraire de confirmations.
