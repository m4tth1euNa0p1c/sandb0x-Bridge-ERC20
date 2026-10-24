---
name: bridge-compose
description: "Implémenter ou auditer les paramètres Docker Compose T3l4N, notamment utilisateurs, volumes, ports et ressources."
---

# Durcir les services Compose

**Entrées.** Fichiers sandbox/compose*.yaml, profils locaux et configuration résolue par Docker Compose.

## Procédure

1. Lire la configuration résolue, pas seulement les ancres YAML : fusion, interpolation et listes peuvent modifier les valeurs réellement appliquées.
2. Vérifier utilisateur non root, absence de privilèges, cap_drop ALL, no-new-privileges, racine en lecture seule et montages d'écriture limités.
3. Contrôler CPU, mémoire, pids, rotation des logs et ports liés à 127.0.0.1. Identifier les chemins de secrets sans en lire le contenu.
4. Après démarrage, comparer docker inspect à l'intention. Ne jamais monter le socket Docker, le répertoire personnel ou un chemin de production dans les services.
5. Vérifier les endpoints publiés depuis l'hôte, même si les conteneurs sont sains. Sur Docker Desktop 28.5.2 testé ici, des services uniquement sur réseaux `internal` ont présenté `NetworkSettings.Ports` vide malgré la publication déclarée. Ne pas généraliser ce comportement à tous les runtimes : relever les ports effectifs et exercer HTTP/RPC sur loopback.
6. Dans cette configuration, les passerelles de `sandbox/loopback_proxy.py` visent chacune une cible fixe et utilisent des réseaux edge séparés sans masquerading. Si ce mécanisme est conservé ou modifié, contrôler qu'il ne devient pas un proxy libre, tester l'accès hôte et rejouer le cloisonnement ; la passerelle n'est pas une exigence universelle de Compose.

**Livrable.** Configuration Compose validée et observations d'application des restrictions.

**Limite.** Tout nettoyage doit utiliser le nom du projet ; aucune commande globale de prune ou de suppression de volumes étrangers.
