---
name: bridge-reseaux
description: "Concevoir ou vérifier les destinations réseau T3l4N entre installation, runtime local et intégration."
---

# Définir les flux réseau autorisés

**Entrées.** sandbox/egress-policy.json, réseaux Compose et dépendances de chaque composant.

## Procédure

1. Séparer les téléchargements d'images et de paquets de l'exécution du bridge ; recenser les destinations effectivement nécessaires à chaque phase.
2. Construire une matrice source, destination, port et motif. Un réseau commun permet généralement davantage que le seul port utile : documenter cette granularité.
3. Pour une allowlist FQDN, identifier le contrôle effectif, ses limites DNS/proxy et les preuves de refus ; ne pas présenter un JSON déclaratif comme un filtre.
4. Vérifier les ports publiés sur loopback et l'absence de chemin de contournement via hôte ou composant multiréseau pour le scénario testé.

**Livrable.** Matrice des flux et séparation claire entre politique voulue et contrôle imposé.

**Limite.** Si le runtime ne peut imposer une destination, consigner la limite plutôt que modifier la promesse de sécurité.
