---
name: bridge-retry
description: "Définir ou tester la politique T3l4N de réessai, attente et intervention."
---

# Borner les réessais et les rejets

**Entrées.** Taxonomie d'erreurs, état persistant des tentatives et limites de fréquence.

## Procédure

1. Classer erreurs transitoires de transport, refus métier, ambiguïtés d'envoi et incohérences RPC ; leur traitement ne doit pas être identique.
2. Persister compteur, prochaine échéance et cause, avec backoff borné et jitter si plusieurs workers partagent le même RPC.
3. Avant de réessayer une soumission ambiguë, réconcilier on-chain ; le budget de tentatives ne remplace pas cette vérification.
4. Tester épuisement des tentatives, redémarrage durant attente et levée manuelle d'un blocage, en gardant l'historique des décisions.

**Livrable.** Table erreur → état → action, bornes et tests de reprise des échéances.

**Limite.** Un rejet définitif ou un besoin d'intervention ne doit pas entrer dans une boucle infinie de diffusion.
