---
name: bridge-manifestes
description: "Produire ou vérifier le manifeste T3l4N d'une campagne réellement exécutée."
---

# Sceller une campagne de preuves

**Entrées.** Commit testé, état Git, configuration non secrète, commandes, résultats et artefacts.

## Procédure

1. Capturer UTC, commit source et empreintes exactes du travail non commité, ainsi que versions, plateforme, images utilisées et configuration effective.
2. Conserver chaque commande structurée, code de sortie, résultat attendu et observé. Les reçus et identités réseau sont ajoutés lorsqu'une transaction a réellement eu lieu.
3. Hacher les artefacts et vérifier leur disponibilité ; documenter exclusions du fingerprint, durée de conservation et emplacement des gros fichiers.
4. Séparer le commit des sources testées de celui du rapport. Vérifier que les sources n'ont pas changé pendant la campagne.

**Livrable.** Manifeste machine-lisible avec chaîne de références et empreintes vérifiées.

**Limite.** Ne pas créer de référence circulaire en affirmant qu'un rapport valide le commit qui l'ajoute.
