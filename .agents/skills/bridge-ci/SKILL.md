---
name: bridge-ci
description: "Implémenter ou revoir la CI T3l4N pour compilation, tests locaux, documentation et détection de secrets."
---

# Vérifier la chaîne automatisée

**Entrées.** Workflow existant, scripts reproductibles et dépendances verrouillées.

## Procédure

1. Réutiliser les commandes locales testées ; distinguer jobs obligatoires locaux et intégrations réelles conditionnelles avec statut explicite.
2. Épingler actions et images lorsque possible, limiter permissions du job et empêcher l'accès aux secrets dans les contributions non fiables.
3. Conserver rapports et codes de sortie même en échec, avec source commit et empreinte ; ne pas masquer une erreur par continue-on-error sur un contrôle obligatoire.
4. Vérifier compilation des composants présents, tests pertinents, build documentaire et scan secrets. Ne pas inventer une compilation de contrats encore absents.
5. Pour un faux positif de scan, relier la valeur à son artefact public vérifié avant toute exception. Les deux empreintes OpenZeppelin AccessControl détectées le 2026-10-24 sont autorisées par valeur exacte et chemin limité ; aucune exclusion globale de sources ou de preuves. Le contrôle positif synthétique doit continuer à échouer avec le code attendu.
6. Tester les images SDK non root et sans réseau avec les répertoires temporaires requis. Sous .NET 10.0.13 Linux, les tests ont besoin d'un `XDG_RUNTIME_DIR` privé inscriptible pour les mutex ; le tmpfs dédié conserve la racine en lecture seule. Un succès sur le SDK hôte ne remplace pas cette exécution.

**Livrable.** Workflow vérifié localement et statut distant seulement s'il a réellement été interrogé.

**Limite.** Ne pas publier, déployer ou pousser simplement pour déclencher une CI sans autorisation correspondante.
