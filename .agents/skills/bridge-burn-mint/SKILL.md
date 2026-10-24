---
name: bridge-burn-mint
description: "Développer ou vérifier le transfert source et la consommation destination du bridge T3l4N."
---

# Implémenter le chemin burn/mint

**Entrées.** ADR du protocole, paire de tokens dédiés et interfaces des contrats existants ou à créer.

## Procédure

1. Sur la source, lier validation des paramètres, burn et émission de l'événement dans la même transaction ; un revert ne doit laisser aucun événement métier exploitable.
2. Sur la destination, vérifier domaine, paire, rôle, limites et identifiant non traité avant mint ; enregistrement du traitement et mint doivent reverter ensemble.
3. Tester l'aller puis le retour avec soldes et totalSupply, en conservant événements et reçus. Ne pas déduire un burn du seul succès d'un appel distant.
4. Décrire explicitement la confiance dans l'exécutant autorisé : il peut demander un mint sans preuve cryptographique de la source si le contrat ne vérifie que son rôle.

**Livrable.** Code et expériences montrant les effets atomiques à l'intérieur de chaque chaîne.

**Limite.** En absence de permissions mint/burn prouvées, refuser l'activation de la paire.
