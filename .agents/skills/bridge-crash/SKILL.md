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
5. Après interruption de session ou du moteur, inspecter d'abord le rapport partiel, `resilience.lock`, les processus actifs, le minage, la pause et la réconciliation. Un verrou persistant n'est pas une autorisation de suppression : confirmer l'absence de campagne active, archiver son contenu et retirer uniquement ce verrou identifié. Ne supprimer ni base ni chaîne pour relancer un test.
6. Si un mint auparavant finalisé disparaît, conserver l'état d'intervention. La reprise opérateur observée a exigé burn canonique, paramètres et domaine exacts, reçu/transaction/effet absents et nonce réservé libre ; elle a conservé le payload, le nonce et le hash puis vérifié crédit unique et offre. Ne pas généraliser ce cas en compensation automatique ni en garantie de durabilité d'Anvil.

**Livrable.** Matrice de points de crash, résultats de reprise et preuves d'absence de mint supplémentaire.

**Limite.** Ne pas supprimer volumes ou transactions ambiguës pour obtenir une reprise apparemment propre.
