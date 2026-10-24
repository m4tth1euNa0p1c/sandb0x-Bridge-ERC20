---
name: bridge-doctor
description: "Exécuter le diagnostic T3l4N pour établir les outils, ressources, accès réseau et restrictions réellement observés sur un hôte."
---

# Diagnostiquer l'hôte et les capacités

**Entrées.** scripts/bridge.py, interpréteur Python, accès en lecture à l'état du moteur et témoins non sensibles.

## Procédure

1. Lancer la commande doctor existante et conserver son code de sortie. Séparer absence d'exécutable, moteur arrêté, refus réseau et manque de ressources.
2. Échantillonner versions, OS, architecture, mémoire et disque disponibles. La disponibilité à l'instant du relevé ne garantit pas celle du prochain démarrage.
3. Tester les restrictions avec des fichiers témoins créés pour l'expérience ; ne jamais explorer des données personnelles pour démontrer un accès hors dépôt.
4. Comparer restrictions déclarées et résultats. Rapporter l'accès large du processus hôte et le caractère partagé du moteur, même lorsque les services sont durcis.
5. Si Docker signale l'épuisement du pool d'adresses, inventorier les sous-réseaux des réseaux existants et les routes de l'hôte, dont le VPN éventuel, avant de choisir un préfixe. Ce défaut a été observé au lancement de local-besu sur le moteur partagé ; il ne justifie aucun nettoyage des réseaux d'autres projets.
6. Le projet utilise actuellement des /28 dans `10.231.240.0/24` et `10.231.241.0/24`, après inventaire local. Vérifier leur absence de collision sur chaque nouvel hôte ; ces préfixes ne sont pas présumés libres partout. Conserver les inventaires utiles et distinguer conflit d'adresse, pool épuisé et port hôte indisponible.

**Livrable.** Rapport UTC de diagnostic, blocages précis et travaux indépendants possibles.

**Limite.** Ne pas installer de logiciel ou changer une politique système sous prétexte de diagnostic sans que cela fasse partie du travail autorisé.
