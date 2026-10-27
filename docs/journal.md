# Journal d'avancement

## 2026-10-24 — ouverture du jalon 1

**Exigence reçue.** Inspecter le dépôt et l'environnement, puis livrer le jalon 1 :
structure, décisions initiales, profils séparés et diagnostic exécuté.

**Observations avant modification.** Le répertoire de travail était vide et hors Git.
Aucun `AGENTS.md` dans ce répertoire ni dans les parents examinés jusqu'à `C:\`.
Le clone HTTPS du dépôt demandé a réussi : dépôt distant vide, aucun travail existant à préserver.
La branche orpheline `codex/bridge-sandbox-evidence` a été créée. Aucun push effectué.

Git 2.52.0.windows.1 et l'authentification GitHub locale sont disponibles.
Docker Desktop répond (Engine 28.5.2, Compose 2.40.3, Linux/WSL2).
Il héberge déjà d'autres conteneurs : ce moteur n'est pas dédié au projet.
Windows 11, 20 processeurs logiques, environ 31,65 Gio de RAM totale et 3,5 Gio
libres lors du premier relevé ; environ 103 Gio libres sur le disque de travail.
Python 3.12.10, uv 0.10.2, SDK .NET 9.0.312 et 10.0.401 disponibles.
Foundry, Anvil, Cast, solc et MkDocs absents du PATH initial.

**Restrictions déclarées de la session.** Accès fichiers sans sandbox, réseau activé,
approbation automatique désactivée (`never`). PowerShell en FullLanguage ; compte
non administrateur Windows. Ces constats ne prouvent aucune isolation du processus hôte.
Un test avec fichier témoin hors dépôt sera conservé par `doctor`.

**Incident d'outillage.** Une première commande d'inventaire PowerShell a échoué
(pipeline appliqué directement à `foreach`). Commande corrigée en stockant le
résultat avant sérialisation. Aucun changement système associé.

**Travail en cours.** ADR, profils et commandes du jalon 1 ; les résultats finaux
seront référencés dans le registre et les manifestes de campagne.

## Vérifications intermédiaires et corrections

Les tests ont détecté puis motivé le refus des politiques de finalité incomplètes,
la séparation statut/environnement d'une preuve, l'intégrité des artefacts et le
refus des montages hors liste. La revue a aussi corrigé les permissions Unix des
témoins et des secrets Compose, et rendu la validation statique obligatoire avant
tout démarrage. Le catalogue demandé comporte 50 agents et 50 skills, sans
modifier les paramètres globaux de Codex.

Premier démarrage local-fast : PostgreSQL, deux Anvil et documentation sains dans
Docker, mais les ports des services exclusivement sur réseaux internes n'étaient
pas publiés effectivement (`NetworkSettings.Ports` vide). Le CLI a échoué sur le
contrôle RPC ; ce démarrage n'a pas été accepté. Trois passerelles de consultation
à cibles fixes, loopback et réseaux edge distincts sans masquerading ont résolu
ce défaut. Les RPC 31337 et 31338 ont ensuite répondu depuis l'hôte.

Le premier lancement Besu a rencontré l'épuisement du pool IPAM du moteur
partagé ; les sous-réseaux /28 du projet ont été explicités après inventaire.
Puis RocksDB a refusé de charger sa bibliothèque JNI depuis `/tmp` noexec
(`UnsatisfiedLinkError: failed to map segment from shared object`). Un tmpfs
exécutable dédié et borné `/jni-tmp` a été ajouté, sans ouvrir la racine en écriture
ni donner des capacités Linux supplémentaires. Les échecs restent distincts
du résultat de la campagne finale.

Première campagne local-fast : 11 contrôles réussis sur le commit 26d03f9.
La campagne Besu suivante a réussi ses contrôles d'infrastructure, mais échoué
au scan : la règle generic-api-key prenait le SHA-256 de l'agent `bridge-secrets`
pour une clé. Détection reproduite en mode verbeux avec valeurs masquées ;
exception restreinte au chemin de manifeste, au champ et au digest exact.
Un contrôle positif synthétique vérifie que le scan continue de détecter les
credentials dans les preuves. Aucun secret réel découvert dans cet incident.

Les rapports JSON sont désormais écrits en LF et `evidence/**` est exclu de la
normalisation de texte Git : leurs empreintes portent sur les mêmes octets après
clone Windows/Linux. Ces changements motivent une nouvelle campagne finale ;
les campagnes antérieures sont conservées comme historiques.

## Clôture technique du jalon 1

Les deux campagnes finales ont réussi leurs 11 contrôles sur `991df1d6d7c5eb0642e9a51501a9018c792aab4a`.
47 tests unitaires et 50 validations de skills ont réussi. Les rapports et le
registre sont mis à jour sans promouvoir le protocole absent. Voir [résultats](resultats.md).

## Mise en œuvre des jalons 2–4 — campagne en cours

Le 2026-10-24, la branche a été poussée sur le dépôt privé ; la CI du jalon 1
`40130621188` a réussi. Les contrats burn/mint ont ensuite été implémentés et
27 tests Foundry ont réussi, avec fuzzing et invariants. La compilation du
signataire et du relayer .NET a réussi ; leurs tests isolés restent distincts
des campagnes EVM/PostgreSQL. Les résultats définitifs seront scellés après
intégration et gel du code.

Incidents observés et corrections :

- Restore Nethereum : Newtonsoft.Json 11.0.2 signalé NU1903, corrigé par le pin
  explicite 13.0.4 ; aucun avertissement correspondant après restore et audit.
- Scan : deux empreintes publiques de fichiers OpenZeppelin assimilées à des
  clés. Exceptions limitées à ces valeurs exactes et chemins de provenance,
  contrôle synthétique positif toujours exécuté. La CI `40131665932` a conservé
  cet échec ; correction poussée ensuite.
- Compte PostgreSQL applicatif : `CREATE SCHEMA IF NOT EXISTS` demandait un droit
  sur la base même après création du schéma par le bootstrap. L'opération
  redondante a été retirée, sans élargir les droits du compte.
- Build Linux du test relayer : le vecteur d'identifiant Solidity n'était pas
  copié dans le contexte de test. Le fichier et son empreinte font désormais
  partie de la construction et du contrôle de fraîcheur.
- Une modification des tests pendant un build a été détectée et le build refusé.
  Les sources applicatives et tests sont gelés avant la nouvelle campagne.
- Revue du déploiement : liaison renforcée entre artefacts compilés et sources
  testées, vérification du réseau avant émission. Le contrôle recherchait
  initialement un reçu sur la mauvaise chaîne : les adresses de contrats
  étaient identiques sur les deux réseaux. La recherche par seule adresse a
  été remplacée par une attribution et une relecture sur le réseau concerné.
  Aucune perte de reçu n'est établie par cet incident. Une expérience isolée
  a en revanche reproduit l'absence de lectures d'état historique après reprise
  sans l'option Anvil de conservation des états historiques.
- La mémoire libre observée de l'hôte est descendue sous 1 Gio. Les serveurs
  de compilation lancés avec le SDK local ont été arrêtés après leurs builds ;
  aucun service extérieur au projet n'a été arrêté.

Les retours ont été intégrés aux skills versions, CI, déploiement, manifestes et
alertes. Le catalogue conserve ses 50 agents et 50 skills ; il ne représente pas
50 processus simultanément actifs.

La révision `r2` démarre avec Anvil 1.8.4 et états historiques conservés ; les
anciennes données synthétiques sont préservées. Un premier aller-retour réel
de 10 tokens a réussi le 2026-10-24 (rapport local horodaté et reçus conservés),
avec soldes restaurés et offre totale égale à la référence. Les 64 tests du
signataire et les 51 tests du relayer passent également dans des conteneurs Linux
sans réseau, non root et à racine en lecture seule. Le runtime 10.0.13 du SDK nécessitait un
répertoire privé `XDG_RUNTIME_DIR` pour son mutex : tmpfs borné ajouté, sans
ouvrir la racine en écriture. Source primaire du comportement :
[dotnet/runtime #135726](https://github.com/dotnet/runtime/issues/135726).

La recette nominale des API et requêtes Grafana/Prometheus ainsi que la capture
du tableau ont été effectuées. Les tests de panne et la compatibilité applicative
Besu sont les étapes suivantes ; le registre attend leur campagne finale.

## Recette complète et contre-revue avant gel

Le premier aller-retour Besu/Anvil a également réussi, avec reçus et soldes
restaurés. Sur local-fast, les neuf scénarios de panne ont passé ; la campagne
diagnostique a correctement refusé une validation globale parce que le code
avait changé pendant l'exécution. Ils doivent être rejoués sur sources gelées.

La contre-revue a reproduit deux faux positifs des gardes : une preuve pouvait
rester valide après échec global, et une option `no-new-privileges:false` pouvait
être confondue avec `true`. Les gardes et leurs régressions ont été corrigées ;
64 tests Python passent. Les conteneurs inspectés utilisaient déjà `true`.

Le premier essai de résilience Besu a passé reprise historique et déduplication,
puis rencontré `WinError10013` lors d'un accès HTTP hôte après levée de pause.
L'instance a retrouvé un état prêt, équilibré, non pausé et sans transfert en
attente lors de trois contrôles. Les comptages TCP observés ne permettent pas
d'attribuer cet incident à une saturation. Aucun pare-feu ni paramètre système
n'a été changé ; l'échec est conservé et la campagne est rejouée.

Les diagrammes Mermaid sont fournis avec un bundle officiel épinglé et sa
licence, sans CDN à l'exécution. Trois diagrammes ont été réellement rendus
par Chrome avec proxy externe fermé et contrôle négatif de connectivité.
La recette d'un tableau Grafana ancien ou arrêté est menée séparément des
contrôles nominaux, avant le gel final.

## Campagnes sur sources figées et incident de reprise

Sur le commit `fd030c49d1e773676e1f3543fff93fa1b60d3c95`, la CI GitHub Actions
40140238460 a installé le projet depuis un clone neuf, puis réussi les 18
contrôles obligatoires de local-fast. Le job d’intégration réelle est ignoré.
L’archive Actions a été téléchargée et son SHA-256 vérifié ; la campagne est
conservée octet pour octet dans `evidence/20261024T225246Z-local-fast/`.
La campagne locale Besu `20261024T231050Z-local-besu` réussit également ses
18 contrôles, dont sept injections réellement exécutées. Les cas gas forcé à
zéro et réorganisation Anvil restent non exécutés sur ce profil.

La correction des permissions Forge sur Linux a été confirmée dans cette CI :
le compilateur suit l’UID non root de l’orchestrateur, lit les sources en lecture
seule et écrit uniquement ses sorties. Trois régressions supplémentaires portent
l’outillage à 67 tests. La supervision a été exercée avec arrêt effectif du
relayer : dernière date connue conservée, valeurs métier indisponibles et
restauration vérifiée. Neuf scénarios promtool comportent 51 assertions.

À la reprise de session, une campagne locale ne possédait aucun manifeste final
et le moteur Docker Desktop était arrêté. Le premier nouveau `prove` échoue
explicitement sur cette indisponibilité (`20261024T230925Z-local-fast`). Aucun
succès n’en est déduit. Après redémarrage du moteur, local-besu retrouve une offre
équilibrée. L’ancienne instance local-fast signale toutefois
`destination_effect_lost_after_policy_finality` sur un transfert.

L’enquête en lecture seule établit un burn source toujours canonique, un bloc
destination remplacé, un reçu et un effet absents, et le nonce réservé 28 encore
libre, sans transaction pending. La cause de l’arrêt du moteur reste inconnue.
Le relayer a bien demandé une intervention et conservé une réconciliation
inconclusive. La procédure opérateur a ensuite arrêté le relayer, revérifié
identités, bytecodes, événement complet, domaine, finalité locale, reçu absent
et nonce libre, puis autorisé uniquement ce transfert à reprendre son état
préparé. Aucun nouveau payload, nonce ou hash n’a été créé. Le processeur
existant a rediffusé la transaction persistée et vérifié le reçu.

Les 22 assertions de cette intervention passent : un seul événement de
complétion, crédit exact, signature/nonce/hash inchangés et offre réconciliée.
L’état avant/après, les commandes SQL ciblées et le script exécuté sont conservés
dans `evidence/restart-incident-20261024/`. Ce n’est pas une réparation automatique
de timeout ni une garantie de durabilité d’Anvil après coupure. Une nouvelle
campagne complète local-fast est lancée sur l’instance ainsi examinée.

Le scan des rapports historiques supplémentaires a signalé des empreintes
publiques et adresses ERC20 dans trois rapports placés à un niveau différent.
Leur rangement a été aligné sur les campagnes habituelles, sans altérer leurs
octets ni les règles Gitleaks. Le scan et les cinq témoins positifs repassent.
Treize instantanés Anvil volumineux (191 010 878 octets) restent à leurs chemins
locaux originaux, référencés et empreintés dans l’index des diagnostics ; ils
sont conservés jusqu’au nettoyage explicite du propriétaire.

La relance local-fast a ensuite rencontré le verrou de la campagne interrompue
à 22:53:21 UTC. Le manifeste 20261024T231823Z-local-fast conserve cet échec
(17 contrôles réussis, résilience refusée). Après vérification qu’aucun processus
de campagne ne restait actif, le seul verrou a été archivé puis retiré. Le rapport
partiel et cette opération sont conservés dans evidence/20261024T225119Z-local-fast/.
Les données du bridge n’ont pas été supprimées pour relancer le test.

La campagne 20261024T232235Z-local-fast a finalement réussi ses 18 contrôles,
avec les neuf injections et un état persistant restauré, sur le même commit
`fd030c49d1e773676e1f3543fff93fa1b60d3c95` que Besu et la CI.
Le registre est recalculé : 21 affirmations vérifiées localement, cinq sur
Besu local, deux bloquées et aucune obsolète. Les champs de définition n’ont
pas changé ; les seuls fichiers de sources modifiés sont les comptes rendus
explicitement exclus de l’empreinte.

## Garde du CLI complet et amélioration des workflows

La commande PowerShell `test --profile local-fast` a terminé avec succès sur
`fd030c4` : 67 tests Python, 27 Solidity, 115 .NET, aller-retour et neuf
injections. Une contre-vérification de main a ensuite reproduit un refus
trop tardif de `build` et `test` avec integration-testnet. Des sentinelles
bloquantes ont empêché toute exécution réelle de ces commandes ; aucun accès
Sepolia ou TELA n’a eu lieu. Le test précédent de up() ne couvrait pas ces
deux branches, donc la formulation NET-001 était trop large.

La garde des sept commandes d’exécution est désormais placée avant leur
travail. Deux régressions vérifient le refus avant processus/RPC et l’acceptation
des profils locaux ; 69 tests Python passent. Les sept CLI réellement invoqués
retournent 2, chacun avec un journal de commandes vide. Le fixture de test
enregistre maintenant son module dynamique dans sys.modules pour exercer
réellement main, sans faux succès causé par un KeyError du fixture.

Les rôles et skills CI et crash intègrent ces retours : couverture du point
d’entrée complet, examen des verrous après interruption, et reprise opérateur
explicitement distincte d’une compensation. Le catalogue 50/50 reste valide.
Les anciennes campagnes sont marquées obsolètes pour les sources modifiées ;
elles restent conservées. De nouvelles campagnes sont requises avant promotion.

## Campagnes finales du code b015e38 — 24 octobre 2026 UTC

Le code figé `b015e387cbbfacc073b4cf0201bc08dae9f464c8` a réussi les
18 contrôles de `prove --profile local-fast` entre 23:41:58 et 23:49:28 UTC,
puis les 18 contrôles de `prove --profile local-besu` entre 23:49:36 et
23:55:48 UTC. Les sources portent l’empreinte
`a78ece60a84e8ebe159c1fd6f817b00ccda800f6002767e8c690126536e7e963`.
Les rapports sont conservés dans `evidence/20261024T234158Z-local-fast/`
et `evidence/20261024T234936Z-local-besu/`.

Chaque campagne comprend 69 tests Python, 27 tests Solidity et 115 tests .NET,
un transfert aller-retour, le cloisonnement, la persistance après arrêt propre,
la supervision et le refus réel des sept commandes d’intégration désactivée.
Les neuf scénarios de panne local-fast réussissent. Les sept exécutables sur
le profil Besu réussissent ; gas forcé à zéro et réorganisation Anvil restent
explicitement non exécutés sur Besu. Le catalogue de 50 rôles et 50 skills
passe sa validation structurelle.

La CI GitHub Actions `40143787185` a également réussi sur ce commit, depuis
un clone Ubuntu neuf avec installation des dépendances. Son job d’intégration
réelle est `skipped`. L’archive téléchargée correspond au SHA-256 publié
par GitHub. Les 16 fichiers de la campagne `20261024T234430Z-local-fast`
ont été extraits sans modifier leurs octets ; leurs empreintes et l’empreinte
des sources ont été vérifiées. Les métadonnées sont conservées dans
`evidence/ci-b015e38/index.json`.

Le registre reflète désormais 21 affirmations vérifiées localement, cinq sur
Besu local et deux blocages externes. Les anciennes campagnes restent
accessibles avec leur version et leur résultat, y compris les échecs.
Les caractères de contrôle introduits involontairement dans quelques lignes
du journal ont été corrigés ; les rapports bruts n’ont pas été réécrits.

Le contrôle final a vérifié les empreintes de toutes les campagnes conservées
et le statut effectif des 28 affirmations. Huit pages HTTP des deux instances
répondent avec succès. Les deux relayers sont prêts, les données récentes,
les bridges non pausés, les interventions à zéro et les offres équilibrées.
La capture Grafana local-fast a été inspectée : identités 31337/31338,
horodatage UTC, absence de retard, réconciliation équilibrée et zéro alerte
active au relevé. Les courbes de panne restent visibles dans l’historique.

Le contrôle d’intégrité a vérifié 294 empreintes, dont les treize instantanés
Anvil hors Git (191 010 878 octets) toujours accessibles à leurs emplacements
référencés. Les trois campagnes complètes du code courant ont la même
empreinte de sources. La validation du registre et des profils ainsi que le
scan Gitleaks passent après ajout des nouveaux rapports ; les cinq témoins
positifs du scanner restent détectés. La documentation stricte est reconstruite
pour servir le registre, les résultats et leurs preuves conservées.

## Expiration du scan sur le dépôt enrichi — 25 octobre 2026 UTC

Le commit de rapports `b394413` a déclenché la CI `40145077211`. Les tests
de contrats, .NET, aller-retour, neuf pannes, cloisonnement, persistance et
supervision réussissent ; le scan de secrets atteint sa limite de 60 secondes
avec environ 52 Mo de preuves versionnées. La campagne conserve donc un
résultat global en échec, 17 contrôles réussis sur 18, sans verdict de sécurité
du scanner interrompu. L’archive téléchargée est conforme au digest GitHub
et la campagne `20261025T000424Z-local-fast` est conservée sans modification.

Décision : porter le budget normal du scan à cinq minutes, conserver une minute
pour les cinq témoins positifs et garder les mêmes restrictions (un CPU,
256 Mio, aucun réseau, montage en lecture seule). Aucun fichier de preuve
n’est exclu pour accélérer le scan. Chaque conteneur reçoit un nom unique et
un label de projet ; un timeout ou une interruption déclenche le nettoyage
de ce seul conteneur avant suppression de sa copie de travail. Un client
Docker interrompu ne garantit pas à lui seul l’arrêt du conteneur.

Trois régressions supplémentaires vérifient le refus sur timeout, la détection
conservée comme échec, et la propagation d’une interruption après nettoyage.
Les 72 tests Python et le catalogue 50/50 passent. Le témoin réel avec limite
injectée de deux secondes retourne 124, supprime son seul conteneur avec code 0,
puis confirme son absence. Le rôle et le skill secrets intègrent ce retour.
Les 26 affirmations précédemment vérifiées sont marquées obsolètes en attente
des nouvelles campagnes ; les deux blocages externes restent inchangés.

Le premier scan après modification a correctement signalé la nouvelle
empreinte publique du rôle `bridge-secrets.toml` dans le témoin de timeout.
La valeur a été comparée au SHA-256 réel du fichier, puis ajoutée à l’exception
existante limitée à ce champ et à ces deux empreintes exactes. Un sixième
témoin aléatoire placé dans ce même champ vérifie qu’une autre valeur reste
détectée. Les cinq témoins précédents restent présents ; aucun élargissement
à un répertoire ou à une classe arbitraire de secrets n’a été ajouté.

## Validation du correctif du scanner — 25 octobre 2026 UTC

Le commit `b97c541fd7cb64a85560ba693742a62304c84885`, d’empreinte
`8ef4e51a3dae091b530d29993fbdeef919431286264bb4e50d34f083258aec2e`,
a réussi les 18 contrôles local-fast entre 00:24:52 et 00:32:48 UTC,
puis les 18 contrôles local-besu entre 00:33:58 et 00:40:29 UTC.
Les 72 tests Python, 27 tests Solidity et 115 tests .NET passent, ainsi que
les neuf scénarios de panne Anvil et les sept exécutés sur Besu. Les deux
cas non exécutés sur Besu restent explicitement distincts des réussites.

La CI `40146594435` du même commit a réussi ses 18 contrôles depuis un clone
neuf. Son scan complet a duré 69,467 secondes, avec deux témoins GitHub et
quatre génériques détectés : la durée observée dépasse effectivement l’ancienne
limite. L’archive reçue a été comparée au digest GitHub, puis la campagne
`20261025T002725Z-local-fast` extraite et ses artefacts vérifiés sans réécriture.
La preuve et l’index sont dans `evidence/ci-b97c541/` ; les campagnes Windows
sont `20261025T002452Z-local-fast` et `20261025T003358Z-local-besu`.

Les sources sont restées inchangées pendant les trois campagnes. Les statuts
effectifs redeviennent 21 vérifications locales, cinq vérifications Besu local
et deux blocages externes. La capture Grafana du correctif a été relue :
disponibilité et données récentes, identités 31337/31338, retard nul,
interventions nulles, bridges actifs, offre équilibrée et aucune alerte active.
L’échec CI antérieur et les deux témoins de timeout restent conservés.

Le relevé de livraison du correctif vérifie les huit pages HTTP, les deux
relayers prêts avec données récentes, les pauses désactivées, zéro intervention
et les deux offres équilibrées. L’audit réalise 368 vérifications d’empreinte,
y compris les treize instantanés hors Git. Le scan final incluant les nouveaux
rapports réussit en 29,969 secondes sur cet hôte et détecte ses six témoins.
Les résultats, commandes, procédures et capture sont indexés dans
`evidence/finalization-b97c541/`. Le dépôt conserve séparément les sources du
correctif et le commit ajoutant ces rapports.

## Incident découvert à la reprise — 27 octobre 2026 UTC

Le diagnostic constate les quatre chaînes arrêtées depuis le 25 octobre,
avec les relayers encore actifs et `ready=false`. Les trois Anvil indiquent
`OOMKilled=true` sous 384 Mio ; Besu sort avec code 1 sans OOM. Les sauvegardes
et deux `pg_dump` sont conservés hors Git, avec empreintes et rétention locale
au moins jusqu'au 27 janvier 2027. Le JSON Besu/Anvil est tronqué. Une copie
candidate garde les champs métier complets et les seules entrées historiques
complètes ; aucun original n'est supprimé.

Les témoins Anvil comparent trois repos de 60 secondes : hauteur stable sans
timer, trente blocs supplémentaires par repos avec l'ancien intervalle. Les
212 et 210 assertions passent, avec deux reprises chacune. Besu reproduit
une sortie 1 lors de la saturation du tmpfs JFR, masquée par le lanceur initial.
Le lanceur officiel `besu-untuned` et le nouveau healthcheck RPC passent leurs
témoins positifs et négatifs. L'attribution historique à JFR reste probable,
car l'occupation du tmpfs réel n'a pas été mesurée avant l'arrêt.

L'audit des copies passe 449 assertions : identités, code, reçus, effets,
nonces, événements exhaustifs et coupes courantes. Le premier audit avait
échoué sur les anciens états historiques absents ; son mauvais nom de sélecteur
de nonce est corrigé dans la seconde procédure, sans réécrire le rapport initial.
La reprise des nœuds conserve aussi un échec transitoire HTTP 502 et sa suite.
L'intervention compare ensuite les observations canoniques et tous les effets
recensés, mine explicitement 129 blocs Anvil sans transaction et vérifie les
lectures du bytecode du bridge et de `nextNonce()` aux 129 hauteurs récentes.
Les checkpoints et en-têtes sont actualisés sous verrous
PostgreSQL, avec empreintes inchangées des quatre tables métier. Le premier
passage Besu échoue sur une requête de logs trop étendue ; la suite utilise
des lots de 512 blocs, comme le relayer, sans augmenter la limite RPC.

Le correctif retire le timer Anvil, borne ses confirmations explicites et
porte son plafond à 1 Gio ; les copies mesurées atteignent environ 519 Mo
de pic cgroup. Dix-neuf tests de garde supplémentaires portent la suite Python
à 91 tests réussis. Une contre-revue en lecture seule ne trouve pas de défaut
bloquant des helpers. Les rôles et skills Anvil/Besu intègrent ces échecs observés ;
le catalogue reste validé à 50/50. La nouvelle valeur publique du hash ERC20,
nommée `token` dans un rapport brut, a déclenché quatre détections : l'exception
reste limitée à cette valeur exacte, avec un septième témoin aléatoire détectable.

Les rapports de diagnostic restent distincts des campagnes complètes à rejouer.
Les affirmations antérieures sont marquées obsolètes. Aucun paramètre Sepolia
ou TELA nouveau n'a été fourni ; ces intégrations restent désactivées.

## Régression de restauration du minage — 27 octobre 2026 UTC

Le commit `eaa5fd46259be53c208e93f1a00c8f3ce53eb172` est poussé, puis la
campagne `20261027T172025Z-local-fast` réussit 17 contrôles sur 18. Le burn
orphelin est observé avant finalité, disparaît de la branche canonique, reste
conservé comme rejet `source_reorg` et ne produit aucun mint. Le contrôle de
nettoyage échoue : automine était actif avant le test et reste désactivé après.
Le setter `evm_setIntervalMining(0)` remplace le mode complet, alors que le
scénario le traitait comme une propriété indépendante. Le rapport reste en
échec ; l'arrêt/recréation du contrôle de persistance rétablit ensuite le mode
déclaré dans Compose. Le rôle et le skill reorg intègrent cet échec observé.
La correction distingue les modes automine, intervalle et manuel et doit
passer le témoin isolé, les tests de garde et la nouvelle campagne complète.

Le témoin isolé reproduit l'ancien ordre incorrect puis réussit 16 assertions
sur les trois modes, avec et sans exception. Les 94 tests Python passent,
dont 22 tests ciblés. Les getters de cette version ne distinguent pas totalement
le mode CLI `Mixed`, exclu des profils contrôlés ; aucune capacité générale
de détection de ce mode n'est revendiquée.

## Limite RPC de la recherche de reçu — 27 octobre 2026 UTC

Le correctif `2b2930c6191f9a515ef6aca07f3f323d56a970a1` réussit les 18
contrôles local-fast (`20261027T172904Z-local-fast`). La campagne Besu
`20261027T173504Z-local-besu` conserve 17/18 : seul le contrôle aller-retour
échoue sur `eth_getLogs`. L'instance dépasse désormais 16 000 blocs ; le helper
de recherche du mint interrogeait tout l'historique en une seule plage, refusée
par Besu. Le relayer utilisait déjà des lots de 512 blocs. La correction étend
cette lecture complète par lots au helper, avec une borne haute fixe et un
délai contrôlé. Les sept scénarios Besu et la persistance réussissent dans la
campagne en échec ; ils ne sont pas promus en livraison complète. Le rôle et
le skill collecte sont précisés à partir de cet écart entre application et outil.

Le rejeu ciblé du 27 octobre à 17:45:40 UTC réussit l'aller-retour Besu :
la recherche du reçu destination Besu parcourt 34 lots et retrouve exactement
un événement canonique. Les 103 tests Python passent, dont neuf nouveaux tests
de pagination. Le catalogue contient toujours 50 agents et 50 skills valides.
Le diagnostic ciblé est conservé dans `evidence/incident-20261027/paginated-mint/` ;
les campagnes complètes sur commit figé restent nécessaires avant promotion.

La contre-revue demande de comparer aussi le hash de transaction du reçu avec
celui du log, pour refuser une réponse RPC incohérente renvoyant une autre
transaction du même bloc. Ce contrôle et son test passent : 104 tests Python
réussis. La CI historique de `2b2930c` a également réussi local-fast ; elle
reste conservée séparément et ne valide pas cette nouvelle correction.

## Scan des sous-dossiers de preuves — 27 octobre 2026 UTC

La campagne `20261027T175230Z-local-fast` sur `ff91b0f` conserve 17/18 :
tous les contrôles métier, pannes, persistance et supervision passent, mais
le scan signale six empreintes de sources dans l'index imbriqué du diagnostic
pagination. Les six valeurs correspondent aux fichiers publics exacts ;
les exceptions existantes ne couvraient qu'un niveau de sous-dossier.
Le correctif conserve ces valeurs et règles exactes et étend le chemin aux
rapports imbriqués. Les sept témoins aléatoires sont désormais injectés dans
un sous-dossier pour vérifier qu'ils restent détectés. Aucun rapport n'est
exclu du périmètre du scan. Le skill secrets intègre ce cas observé.

Le scan CLI du 27 octobre à 18:01:30 UTC réussit : aucune détection sur les
fichiers versionnables, puis deux témoins GitHub et cinq témoins génériques
détectés dans le sous-dossier. Le catalogue 50/50 reste valide. Le journal
de commande masqué est conservé dans le dossier d'incident.

## Attente de reprise Prometheus — 27 octobre 2026 UTC

La CI `ff91b0f` conserve 17/18 pour une autre raison : `live.py` échoue sur
le contrôle `bridge_ready` après la reprise du relayer. Le redémarrage commence
à 18:01:49 UTC ; le test annonce la reprise à 18:01:51, avant son échec nominal
à 18:01:51.813. L'attente vérifiait seulement `up=1` et la fraîcheur, alors que
le relayer peut exposer un horodatage frais avec `Ready=false` au démarrage.
L'absence d'attente de `bridge_ready=1` est confirmée dans le test. La valeur
numérique et l'heure exacte du scrape fautif n'étaient pas enregistrées ;
la course est fortement étayée, pas une reconstitution exhaustive de ce scrape.
L'archive et ses 17/18 sont conservés dans `evidence/ci-ff91b0f-failed/`.

La campagne Windows `20261027T180236Z-local-fast` du commit `fcf546a` réussit
18/18, de 18:02:36 à 18:08:47 UTC. La course d'observation n'est donc pas
systématique ; cette réussite n'annule pas l'échec CI antérieur. Le rôle et
le skill Grafana sont précisés pour attendre la disponibilité métier collectée,
conserver les observations et tester ce décalage de démarrage.

Le correctif passe 108 tests Python. Le rejeu réel d'arrêt/reprise du relayer
se termine à 18:12:27 UTC, sources inchangées. Il conserve six observations :
l'API est déjà prête alors que Prometheus ne dispose pas encore de toutes les
séries, puis `up`, fraîcheur et `bridge_ready` atteignent ensemble 1. Le test
nominal HTTP passe ensuite. Le cas précis `up/fresh=1, ready=0` et son timeout
persistant restent couverts par les tests contrôlés, distincts de ce rejeu réel.
