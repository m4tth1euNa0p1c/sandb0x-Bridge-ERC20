---
name: bridge-alertes
description: "Définir et tester les règles d'alerte T3l4N à partir de métriques réellement disponibles."
---

# Évaluer les alertes d'exploitation

**Entrées.** Séries exposées, cadence de collecte, politique de finalité et procédures d'incident.

## Procédure

1. Relier chaque alerte à une action opérateur : collecte figée, ancienneté excessive, épuisement de gas, écart de réconciliation ou service absent.
2. Traiter explicitement données manquantes et données anciennes ; un zéro peut masquer un exporteur arrêté.
3. Choisir seuils et durées avec leur justification mesurée ou projetée, puis tester séquences de valeurs et redémarrage de compteur.
4. Vérifier la résolution de l'alerte et le lien vers la procédure correspondante ; ne pas activer d'envoi externe non demandé.
5. Exécuter `promtool test rules` avec un espace temporaire explicitement inscriptible et borné : l'outil crée une TSDB temporaire. L'échec constaté le 2026-10-24 sous racine en lecture seule a été corrigé par un tmpfs `/tmp`, sans rendre la racine inscriptible.
6. Tester l'unicité des séries de fallback : `or vector(0)` sans correspondance de labels peut afficher simultanément la mesure et un faux zéro. Contrôler les labels et les cas absent, périmé et non prêt.
7. Vérifier le tableau réellement servi et son rendu visuel, pas seulement le JSON provisionné. Pour les bind mounts dont les événements ne remontent pas, Grafana exige un intervalle de provisioning strictement supérieur à 10 secondes pour le polling ; 30 secondes ont corrigé l'observation locale.

**Livrable.** Règles testées, seuils justifiés et runbook lié à chaque alerte.

**Limite.** Une règle chargée sans scénario de déclenchement ne constitue pas une preuve de détection.
