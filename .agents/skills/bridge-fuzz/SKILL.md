---
name: bridge-fuzz
description: "Ajouter du fuzzing Foundry T3l4N pour explorer les paramètres de transfert et les frontières des contrats."
---

# Construire des propriétés de fuzzing

**Entrées.** Contrats implémentés, règles métier et configuration Foundry verrouillée.

## Procédure

1. Définir des propriétés observables à partir du protocole : conservation locale burn/mint, domaine du transfert et absence d'effet après rejet.
2. Choisir bornes et assume sans exclure les entrées qui exposent le défaut ; inclure adresses nulles, montants limites et variations de contexte.
3. Conserver seed, nombre de runs, contre-exemple réduit et versions ; transformer chaque défaut découvert en régression ciblée avant correction.
4. Vérifier que le test appelle le code du contrat avec un oracle indépendant ; recopier l'algorithme d'identifiant dans le test n'est pas une validation indépendante.

**Livrable.** Suite fuzz exécutée et contre-exemples reproductibles lorsqu'ils existent.

**Limite.** Un nombre de runs élevé ne justifie pas une preuve exhaustive ni la validation d'un chemin jamais atteint.
