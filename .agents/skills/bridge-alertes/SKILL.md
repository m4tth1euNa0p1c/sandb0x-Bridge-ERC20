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

**Livrable.** Règles testées, seuils justifiés et runbook lié à chaque alerte.

**Limite.** Une règle chargée sans scénario de déclenchement ne constitue pas une preuve de détection.
