---
name: bridge-secrets
description: "Inspecter les fichiers et flux T3l4N pour éviter clés, identifiants et paramètres sensibles dans Git ou les preuves."
---

# Contrôler la circulation des secrets

**Entrées.** Diff versionnable, liste des chemins de secrets et paramètres des outils de collecte.

## Procédure

1. Scanner les fichiers destinés au commit avec un outil en mode redact ; ne pas monter l'ensemble du répertoire personnel ou lire les secrets locaux pour les comparer.
2. Vérifier arguments de processus, variables sérialisées, URL RPC authentifiées et captures. Un secret masqué dans une console peut rester dans un artefact brut.
3. Contrôler les montages par service et les permissions hôtes. Les secrets Compose sur fichiers ne sont pas un coffre ni une protection contre l'opérateur Docker.
4. En cas de fuite réelle, retirer l'exposition immédiate et signaler la nécessité de révocation/rotation ; ne pas considérer la suppression du fichier comme réparation complète.
5. Conserver un timeout comme échec de vérification. Dimensionner un budget borné pour le volume des preuves sans exclure ces fichiers du scan. Identifier chaque conteneur de scan par un nom unique et un label de projet ; après timeout ou interruption du client Docker, arrêter uniquement ce conteneur avant de retirer sa copie de travail. Rejouer un témoin de timeout et les témoins positifs de détection.
6. Une empreinte de source publique peut déclencher un motif de clé. Comparer sa valeur au fichier exact avant toute exception ; limiter celle-ci à la règle, au chemin et à la valeur vérifiée. Exercer les témoins aléatoires aussi dans un sous-dossier de preuves : la profondeur d'un rapport ne doit ni le soustraire au scan ni masquer des valeurs nouvelles.

**Livrable.** Rapport de scan sans valeurs sensibles et corrections des chemins d'exposition.

**Limite.** Ne jamais afficher le secret détecté pour prouver la détection.
