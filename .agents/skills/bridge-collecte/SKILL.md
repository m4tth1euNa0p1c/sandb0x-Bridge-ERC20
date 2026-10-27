---
name: bridge-collecte
description: "Implémenter ou vérifier la collecte T3l4N à partir des logs historiques des chaînes sources."
---

# Collecter historiquement les événements

**Entrées.** Adresse bridge vérifiée, ABI d'événement, plage de blocs et checkpoint persistant.

## Procédure

1. Utiliser eth_getLogs par fenêtres bornées avec reprise historique ; les notifications WebSocket peuvent accélérer mais ne doivent pas être la seule source.
2. Conserver chain ID, adresse, blockNumber, blockHash, transactionHash et logIndex avec les données métier et l'état de finalité.
3. Ne faire avancer le checkpoint qu'après persistance atomique des événements de la fenêtre ; rejouer une fenêtre en chevauchement lors de la reprise.
4. Traiter limites de plage, réponses tronquées ou incohérentes comme erreurs observables ; vérifier que les bornes inclusives ne sautent ni ne doublent un bloc.
5. Appliquer aussi la pagination aux scripts de démonstration, recherches de reçus et procédures opérateur. Un petit déploiement neuf peut masquer le défaut : tester un événement au-delà de la première plage sur un historique dépassant la limite RPC. Capturer une borne haute fixe, conserver tous les résultats et refuser explicitement timeout, doublon ou réponse hors filtre.

**Livrable.** Collecteur réessayable, logs conservés et expérience d'événements produits pendant une interruption.

**Limite.** Ne pas convertir une erreur RPC en fenêtre vide validée.
