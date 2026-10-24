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

**Livrable.** Rapport de scan sans valeurs sensibles et corrections des chemins d'exposition.

**Limite.** Ne jamais afficher le secret détecté pour prouver la détection.
