# T3l4N-Bridge-ERC20 — règles de travail

## Périmètre

Démonstrateur de test ERC20 bidirectionnel. Documentation et comptes rendus en français.
La demande initiale et les jalons sont tracés dans `docs/exigences.md`.
Branche de travail : `codex/bridge-sandbox-evidence`. Ne pas fusionner vers main,
publier de documents privés ou pousser sans demande explicite.

## Méthode

- Lire les consignes applicables et l'état Git avant toute modification ; préserver les travaux existants.
- Suivre exigence → ADR → code → test → preuve conservée → documentation.
- Ne jamais transformer un test absent, ignoré ou bloqué en réussite.
- Séparer simulation Anvil, Besu local, Sepolia et véritable TELA de test.
- Ne deviner aucun paramètre TELA, rôle, token, consensus, RPC ou droit de déploiement.
- Aucun mainnet, actif réel, secret dans Git, clé dans les logs ou usage de comptes Anvil publics sur réseau partagé.
- Modèle initial : tokens de test dédiés, burn/mint avec relayer autorisé ; ce dernier ne prouve pas cryptographiquement le burn.
- Aucune promesse de certification, de conformité bancaire ou de préparation à la production.

## Exécution et compartimentage

- Les opérations locales réversibles nécessaires sont autorisées ; signaler les vrais blocages et poursuivre le travail indépendant.
- Les processus hôtes et le moteur Docker ont des droits étendus. Les restrictions Compose ne confinent pas Codex.
- Ne monter ni répertoire personnel, ni socket Docker, ni identifiants de production dans les services.
- Conteneurs non privilégiés, non root, capacités supprimées, no-new-privileges, racine en lecture seule,
  volumes d'écriture explicites et ressources bornées lorsque le runtime le permet.
- Ne nettoyer que les ressources portant le nom et les labels de ce projet. Aucun prune global.
- Installation de dépendances et exécution sont deux phases distinctes ; ne pas qualifier une liste déclarative de pare-feu.

## Preuves

- Conserver commandes, codes de sortie, horodatage UTC, source commit, état Git,
  empreintes exactes des sources, versions, images, configuration non secrète et artefacts.
- Le commit testé précède le commit ajoutant son rapport. Aucun rapport ne prétend se valider lui-même.
- Une modification pertinente rend la preuve obsolète jusqu'à une nouvelle campagne.
- Le registre `docs/claims.yaml` distingue proposé, implémenté, vérifié_local,
  vérifié_besu_local, vérifié_sepolia, vérifié_tela, bloqué et obsolète.
- L'état projet et l'exploitation affichent la date des données ; une observation historique n'est pas du direct.

## Vérifications

Exécuter les commandes réellement disponibles dans `README.md`. Les tests du jalon 1
portent sur l'outillage, les configurations et l'infrastructure ; ils ne valident pas le bridge.
Ajouter les tests de protocole et de reprise avec leur implémentation aux jalons suivants.
