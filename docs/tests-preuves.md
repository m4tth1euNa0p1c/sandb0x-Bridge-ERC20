# Tests et chaîne de preuve

## Campagne du jalon 1

`prove` exécute tests d'outillage, validation des deux Compose, construction
documentaire stricte, scan Gitleaks, démarrage du profil, inspection runtime,
cloisonnement, persistance après arrêt/recréation et refus de l'intégration.
Chaque vérification a un résultat attendu, un résultat observé et un booléen réel.
Une exception rend la vérification en échec. Les tests applicatifs absents sont
énumérés dans `not_executed` et ne deviennent pas des réussites.

Chaque répertoire `evidence/<UTC>-<profil>/` contient `manifest.json`, son SHA-256,
les commandes et codes de sortie, les empreintes des artefacts, les versions,
digests/IDs des images, configuration non secrète, état Git et inventaire SHA-256
des sources. La preuve ne constitue pas une attestation d'une autorité indépendante.

`source_commit` désigne le commit préalable au rapport. Le registre, le journal,
le résumé des résultats et `evidence/` sont exclus de l'empreinte des **sources de
comportement** pour permettre l'ajout du rapport sans cercle. La formulation,
le périmètre, les hypothèses et la méthode de chaque affirmation sont eux-mêmes
empreintés. Les autres docs, les agents et les skills font partie des sources.
Le tableau recalcule l'état effectif : code, définition, environnement ou artefact
modifié ⇒ affirmation obsolète. Aucune remise à zéro implicite des preuves.

Conservation : manifestes et rapports légers pendant la vie du dépôt. Le site
généré, les caches d'images et les volumes restent locaux jusqu'au nettoyage
explicite du propriétaire. Toute future grosse trace devra avoir URI, empreinte
et durée de conservation avant de soutenir une affirmation.

## Matrice applicative à réaliser

Tous les scénarios de cette section sont **non exécutés** au jalon 1.

| Scénario | Assertion attendue | Jalon |
|---|---|---|
| Aller et retour | Soldes entiers et bénéficiaire exacts ; somme réconciliée | 2 |
| Zéro, limites, mauvais destinataire, decimals incompatibles | Rejet explicite sans variation d'offre | 2 |
| Appel non autorisé | Revert, aucune émission | 2 |
| Log livré plusieurs fois | Une seule entrée métier et un seul mint | 2–3 |
| Rejeu sur autre chaîne/bridge/paire | Domaine refusé | 2 |
| Pause et reprise | Aucun crédit pendant pause, reprise maîtrisée | 2 |
| Interruption de collecte | Historique rattrapé sans omission ni doublon | 3 |
| RPC indisponible, lent ou incohérent | État d'attente/échec borné, pas de crédit prématuré | 3 |
| Crash autour de persistance et envoi | Réconciliation du hash/nonce et aucun effet dupliqué | 3 |
| Réponse d'envoi perdue | Reçu/processed vérifiés avant réémission | 3 |
| Workers concurrents | Un travail réservé et nonce unique | 3 |
| Gas insuffisant | Échec classé, aucune compensation automatique | 3 |
| Redémarrage persistant | Checkpoints et états retrouvés | 3 |
| Reorg Anvil avant finalité | Log orphelin exclu, aucun mint associé | 3 |
| Fuzzing et invariants | Conservation, plafonds et anti-rejeu pour entrées générées | 3 |
| Réconciliation dans les deux sens | Transit dédupliqué, émissions externes explicites | 3 |
| Même bytecode sur Besu London | Comportements de contrat identiques dans le périmètre testé | 4 |
| Sepolia puis TELA de test | Identités, finalité, rôles et reçus réellement observés | 5 |

La CI du jalon 1 compile les scripts Python, teste l'outillage et les catalogues,
construit les docs et exécute la campagne local-fast. Elle ne prétend pas compiler
des contrats ou un relayer absents. L'intégration testnet est un job distinct
explicitement désactivé. Une exécution locale du workflow ne prouve pas qu'un run
GitHub Actions a eu lieu ; la publication n'est pas effectuée ici.
