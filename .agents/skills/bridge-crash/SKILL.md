---
name: bridge-crash
description: "Tester la reprise T3l4N après arrêt brutal entre persistance et opérations RPC."
---

# Injecter des crashs aux frontières

**Entrées.** Chemins d'exécution instrumentables, stockage persistant et transferts de test.

## Procédure

1. Positionner les points de crash avant/après commit de collecte, réservation de nonce, persistance de signature, diffusion et lecture du reçu.
2. Arrêter effectivement le processus ou conteneur au point choisi ; un mock qui retourne une erreur ne reproduit pas forcément un crash sans finally.
3. Redémarrer avec la même base et les mêmes identités de chaîne, puis vérifier la machine à états et le nombre d'effets destination.
4. Conserver ordre des événements et bornes temporelles ; répéter le point où une transaction a pu partir avant la dernière écriture locale.

**Livrable.** Matrice de points de crash, résultats de reprise et preuves d'absence de mint supplémentaire.

**Limite.** Ne pas supprimer volumes ou transactions ambiguës pour obtenir une reprise apparemment propre.
