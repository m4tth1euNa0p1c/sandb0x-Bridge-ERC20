---
name: bridge-grafana
description: "Créer ou vérifier un dashboard Grafana T3l4N alimenté par des métriques existantes."
---

# Construire les tableaux d'exploitation

**Entrées.** Sources Prometheus, catalogue de métriques, fréquence de rafraîchissement et utilisateurs prévus.

## Procédure

1. Séparer santé de service et état du protocole ; montrer dernier succès de collecte, attente, erreurs, gas, pause et réconciliation seulement lorsqu'instrumentés.
2. Afficher unités, profil, réseau et heure d'observation ; rendre visibles les séries absentes et les données anciennes au lieu de panneaux faussement verts.
3. Provisionner datasource et dashboard depuis des fichiers versionnés, sans secret ni identifiant de transfert dans les variables de série.
4. Vérifier visuellement les états nominal, arrêt et dégradation avec une fenêtre temporelle adaptée ; conserver l'identifiant et la version du tableau.
5. Une série instantanée disparaît après arrêt du scrape : conserver explicitement le dernier horodatage dans une fenêtre historique bornée, sans réutiliser les mesures métier périmées comme état courant. Tester marqueur stale et expiration de fenêtre. Mapper les valeurs nulles en couleur neutre ; une absence verte a été observée puis corrigée dans ce projet.

**Livrable.** Dashboard reproductible et résultats des scénarios visuels observés.

**Limite.** Ne pas présenter un export statique ou un panel sans datasource comme supervision en direct.
