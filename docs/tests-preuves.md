# Tests et chaîne de preuve

## Lire les résultats

La référence de livraison est [la page des résultats](resultats.md) et le
[registre des affirmations](claims.yaml). Cette page décrit les vérifications
implémentées ; elle n'attribue pas par anticipation le statut d'une campagne
réseau encore à sceller. Un test absent, ignoré ou non exécuté ne valide rien.

Les premiers tests isolés réellement exécutés ont donné 27 tests de contrats,
64 tests de signataire et 51 tests de relayer réussis. Les rapports locaux
sont `.local/contracts-verification.json` et les TRX sous `.local/test-results/`.
Les nombres et sources de la dernière campagne priment sur ce relevé
préparatoire. Les tests .NET isolés utilisent des doubles RPC et stockage :
ils ne démontrent pas seuls la persistance PostgreSQL ni deux nœuds réels.

## Matrice de vérification

| Domaine | Vérification présente et assertion attendue | Registre |
|---|---|---|
| Contrats et montants | Burn/mint atomiques, allowance, bénéficiaire et unités exacts, rôle refusé, token/decimals non pris en charge rejetés | CONTRACT-001 |
| Domaine et doublons | Vecteur Keccak indépendant, mutation des champs, rejeu et completion répétée sans second mint | CONTRACT-001 |
| Fuzzing / invariants | Deux fuzz tests à 1 000 exécutions ; deux invariants stateful, 256 séquences de profondeur 64, actions réellement atteintes | CONTRACT-001 |
| Signature | Authentification HTTP, format, domaine, montants, gas, fréquence, signatures récupérables et erreurs sans secret | SIGN-001 |
| Collecte et reprise isolées | Historique, hashes, checkpoints, nonce durable, reçus et `processed`, pannes RPC et limite de tentatives | RELAYER-001 |
| Aller-retour réel | Deux transactions source et deux mints destination, soldes attendus puis offre au repos | TRANSFER-001 |
| Interruption réelle | Burn pendant arrêt, absence de collecte pendant arrêt, rattrapage historique après redémarrage | RESILIENCE-001 |
| Recollecte réelle | Checkpoint reculé ; une entrée métier, même nonce/hash, aucune nouvelle émission | RESILIENCE-001 |
| Pause / gas / RPC | États ou dégradation attendus avant reprise ; montant unique après restauration | RESILIENCE-001 |
| Concurrence réelle | Deux processus, nonces distincts pour transferts distincts et un effet par ID | RESILIENCE-001 |
| Crash réel | Sorties 91/92 après signature durable ou diffusion ; reprise du même nonce/hash et mint unique | RESILIENCE-001 |
| Réorg préfinalité | Burn observé, snapshot restauré, nouveau hash de bloc, observation non canonique et absence de mint | RESILIENCE-001 |
| Offre | Coupes couvertes et causalement cohérentes, deux sens, déduplication et incohérence explicite | RECON-001 |
| Cloisonnement | Accès autorisé réussi, route interdite refusée, témoin hors périmètre absent, secrets limités aux besoins | ISO-001, ISO-002, KEY-001 |
| Supervision | Règles Prometheus, données absentes/anciennes, API Grafana et disponibilité réelle | OBS-001 |
| Besu local | Contrats et chemins métier exécutés sur la configuration Besu verrouillée | BESU-PROTO-001 |
| Sepolia / véritable TELA | Identités, permissions, finalité, fonds et reçus externes | Bloqué ; aucune exécution annoncée |

L'invariant de conservation des contrats exclut les émissions externes et la
fraude de l'exécuteur. Les appels `vm.chainId` de Forge partagent un EVM de test ;
ils ne remplacent pas deux nœuds RPC. Une réorg Anvil ne démontre aucune finalité TELA.

Le crash `after_broadcast` intervient après une réponse RPC positive et avant
l'écriture de submitted. Il exerce l'ambiguïté de reprise sans supprimer une
réponse réseau. Le cas « transaction envoyée mais réponse perdue » existe aussi
dans les tests isolés du relayer ; cette différence de méthode reste visible.

## Exécution reproductible

Après installation des images et dépendances verrouillées :

```sh
python contracts/tools/verify.py
python scripts/bridge.py test --profile local-fast
python scripts/bridge.py prove --profile local-fast
python scripts/bridge.py prove --profile local-besu
```

`test` combine outillage, contrats, tests .NET, démarrage local, aller-retour et
résilience. `prove` ajoute documentation, scan, contrôles d'infrastructure,
cloisonnement, supervision et manifeste. Les commandes conservées sont la
référence exacte de la version testée.

`tests/resilience.py` réserve le profil avec un fichier de verrou, conserve
chaque tentative dans `.local/resilience/` et arrête les scénarios suivants
après échec. Les mutations sont restaurées dans des blocs `finally`. Le gas
forcé à zéro et la réorg Anvil restent `not_executed` sur local-besu ;
ils ne deviennent jamais des validations Besu.

Les contrats utilisent un compilateur verrouillé dans un conteneur Forge sans
réseau. Le rapport contient les empreintes des sources, des artefacts exacts,
des ABI canoniques et des bytecodes. Le runtime de Bridge avant déploiement
contient des emplacements d'immuables ; son hash diffère de l'empreinte du code
effectivement déployé, interrogée séparément sur chaque chaîne.

## Manifestes, obsolescence et conservation

Chaque `evidence/<UTC>-<profil>/` conserve manifeste, empreinte, commandes,
codes de sortie, versions, images observées, configuration non secrète,
identités réseau, reçus applicables et hashes des artefacts. L'état Git et les
empreintes exactes complètent le commit source, même avec un répertoire modifié.

Le commit du code testé précède le commit du rapport. Le registre, le journal,
le résumé des résultats et `evidence/` sont exclus de l'empreinte des sources
de comportement pour éviter une référence circulaire. La formulation, le
périmètre, les hypothèses et la méthode de l'affirmation sont aussi empreintés.
Les autres docs, agents et skills font partie des sources prises en compte.

Le tableau recalcule l'état effectif : modification pertinente du code, de la
définition, de l'environnement ou d'un artefact ⇒ preuve obsolète jusqu'à nouvelle
vérification. Une ancienne réussite ne valide pas la version courante. Les
statuts distinguent proposé, implémenté, vérifié_local, vérifié_besu_local,
vérifié_sepolia, vérifié_tela, bloqué et obsolète.

Les rapports légers et manifestes du dépôt sont conservés pendant sa durée de
vie. Les rapports de travail `.local`, volumes, caches et captures restent
locaux jusqu'au nettoyage explicite de l'opérateur ; toute preuve utilisée
doit être copiée/référencée et hachée dans la campagne. Un artefact volumineux
externe doit avoir URI accessible, empreinte et durée de conservation déclarée.

La CI exécute les commandes versionnées dans `.github/workflows/`. Une validation
locale de ces commandes n'est pas une exécution GitHub Actions. Les tests
d'intégration externe conservent un statut distinct lorsqu'ils ne sont pas exécutés.
