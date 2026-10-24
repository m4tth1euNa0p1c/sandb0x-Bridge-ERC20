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
5. Conserver séparément hash du fichier compilé, ABI canonique, bytecode de création, gabarit du runtime et runtime réellement déployé. Les immutables Solidity peuvent rendre différents ces deux derniers objets ; ne pas les intervertir.
6. Refuser le statut vérifié si la campagne a échoué ou si le contrôle de stabilité des sources a échoué, même lorsque le checkout retrouve ensuite l'empreinte de départ. Le retour à des octets identiques ne répare pas une expérience interrompue par une modification.

**Livrable.** Manifeste machine-lisible avec chaîne de références et empreintes vérifiées.

**Limite.** Ne pas créer de référence circulaire en affirmant qu'un rapport valide le commit qui l'ajoute.
