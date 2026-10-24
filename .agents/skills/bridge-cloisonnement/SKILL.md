---
name: bridge-cloisonnement
description: "Exécuter les tests témoins de cloisonnement T3l4N après changement de réseaux, volumes ou secrets."
---

# Prouver les frontières d'isolation

**Entrées.** Conteneurs du projet, ressources témoins non sensibles et accès d'orchestration au moteur.

## Procédure

1. Commencer par un contrôle positif : rendre une ressource témoin accessible depuis le compartiment autorisé pour éliminer un faux refus dû à son absence.
2. Tester ensuite la même cible par adresse IP depuis le compartiment interdit, afin de distinguer filtrage et simple échec DNS.
3. Vérifier fichier hors périmètre, secret propre lisible et secret d'un autre compartiment absent. Ne jamais utiliser une vraie clé comme témoin.
4. Conserver commandes, erreurs, état réseau et cleanup ciblé. Un refus observé sur une cible donnée ne prouve pas toutes les sorties réseau.

**Livrable.** Assertions positives et négatives avec résultats bruts et portée exacte de la preuve.

**Limite.** Interrompre une conclusion de cloisonnement si le contrôle positif échoue ou si la cible disparaît entre les essais.
