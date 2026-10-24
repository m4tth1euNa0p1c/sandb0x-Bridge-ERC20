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

**Livrable.** Workflow vérifié localement et statut distant seulement s'il a réellement été interrogé.

**Limite.** Ne pas publier, déployer ou pousser simplement pour déclencher une CI sans autorisation correspondante.
