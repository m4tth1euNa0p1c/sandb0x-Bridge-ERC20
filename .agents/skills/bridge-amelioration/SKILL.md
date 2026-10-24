---
name: bridge-amelioration
description: "Réviser un agent ou skill T3l4N après usage, erreur observée ou ambiguïté démontrée."
---

# Améliorer les agents et les skills par preuve

**Entrées.** Demande d'origine, instruction utilisée, comportement observé et résultat de l'expérience.

## Procédure

1. Isoler l'écart concret : routage erroné, prérequis oublié, action excessive ou conclusion sans preuve. Ne pas ajouter une règle générale sur un risque seulement hypothétique.
2. Modifier le plus petit périmètre de description ou procédure qui traite cet écart ; préserver les autorisations et les objectifs du projet.
3. Rejouer un cas représentatif et un cas voisin qui ne doit pas déclencher le skill. Conserver avant/après, résultat et limites de la validation.
4. Exécuter scripts/validate_capabilities.py après modification, et le validateur de skill disponible si nécessaire. Une validation syntaxique ne démontre pas la qualité du raisonnement.
5. Consigner l'amélioration dans le journal du projet avec une prochaine vérification motivée. Le cycle se poursuit lors des sessions ou automatisations autorisées, sans promesse de fonctionnement perpétuel.

**Livrable.** Correction ciblée, résultat de validation et retour d'expérience traçable.

**Limite.** Ne pas réécrire automatiquement les 50 skills à chaque usage ni déclarer une amélioration sans effet observé.
