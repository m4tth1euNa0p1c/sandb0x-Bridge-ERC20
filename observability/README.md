# Supervision locale

Prometheus collecte le relayer toutes les 5 secondes et Grafana interroge
Prometheus. Le tableau `t3l4n-bridge` est provisionné depuis
`grafana/dashboards/bridge.json`. Le contrat exact des séries se trouve dans
[metrics-contract.md](metrics-contract.md).
Le provisionnement relit les fichiers toutes les 30 secondes ; une modification
de la configuration du fournisseur exige un redémarrage de Grafana. Prometheus
doit également être redémarré pour prendre en compte ses règles modifiées dans
ce profil, qui n'expose pas l'API de rechargement.

| Profil | Prometheus | Grafana |
|---|---|---|
| local-fast | http://127.0.0.1:18090 | http://127.0.0.1:13000/d/t3l4n-bridge |
| local-besu | http://127.0.0.1:18091 | http://127.0.0.1:13001/d/t3l4n-bridge |

Ces adresses ne sont utilisables que lorsque les services correspondants sont
démarrés. La commande de démarrage complète relève de `../README.md` et du profil
Compose. `compose.monitoring.yaml` ne démarre ni les chaînes ni le relayer à lui
seul. Aucun profil Sepolia/TELA n'est activé par ce module.

## Données et limites

Le tableau montre disponibilité du scrape, état prêt, fraîcheur, version, profil,
chain IDs, collecte, retard, états de transfert, tentatives, erreurs, gas, pause
et contrôle d'offre. L'heure UTC de la dernière observation reste visible après
arrêt pendant une fenêtre de 24 heures, sous réserve de sa présence dans Prometheus.
Au-delà, elle devient « Indisponible ». Les valeurs courantes métier disparaissent après 30 secondes sans
instantané récent ou si le relayer n'est pas prêt ; elles affichent
« Indisponible ». Le contrôle d'offre possède aussi une limite propre de 60 secondes.
Les courbes sont historiques
et portent ce qualificatif. L'actualisation automatique de la page n'établit pas
à elle seule la fraîcheur des données.

La version est celle injectée au processus, pas une validation de campagne.
La vue projet dans la documentation, `docs/claims.yaml` et `evidence/` reste la
référence pour les tests exécutés, blocages et preuves obsolètes. Aucune métrique
de certification ou de performance projetée n'est fabriquée. Une réconciliation
équilibrée reste conditionnée aux hypothèses documentées du contrôle comptable.

Prometheus conserve au plus 24 heures de séries, avec un objectif de 128 MB de
blocs TSDB. Cette option ne borne pas à elle seule tous les fichiers temporaires
et le WAL ; le volume doit être surveillé par l'hôte. Grafana conserve sa base
interne dans un volume propre. L'arrêt des services arrête l'observation ; la
disponibilité future dépend de l'hôte et de son redémarrage explicite.

## Compartiments

`sandbox/compose.monitoring.yaml` utilise les images et digests du verrou
`sandbox/versions.lock.json`. Les utilisateurs constatés dans les images sont
65534 pour Prometheus et 472 pour Grafana ; le service Grafana impose aussi GID472.
Les volumes nommés reprennent les répertoires de données de leurs images.
Les racines sont en lecture seule, les capacités supprimées et
`no-new-privileges` activé. CPU, RAM, processus, `/tmp` et journaux sont bornés.

Les deux applications sont uniquement sur le réseau interne `monitoring`.
Des passerelles HTTP à cible fixe publient les consultations sur 127.0.0.1 ;
chacune possède son réseau edge sans masquerading. Les sous-réseaux `.160/28`
et `.176/28` complètent les plages de chaque profil. Cette configuration doit
être recettée depuis l'hôte et par les tests de cloisonnement : le YAML seul
n'établit pas l'efficacité de l'isolation sur un autre moteur.

Grafana reçoit uniquement `grafana_password` depuis le répertoire runtime.
Il ne reçoit aucune clé de signature, aucun secret PostgreSQL ni socket Docker.
La consultation locale anonyme est autorisée avec le rôle Viewer ; les
dashboards et la datasource ne sont pas modifiables par ce rôle. Le formulaire
de connexion est désactivé. Les mises à jour automatiques, le préchargement de
plugins, la télémétrie et Grafana Live sont désactivés. Aucun Alertmanager,
destinataire externe ni envoi de message n'est configuré.

## Vérifications reproductibles

Installer les images verrouillées pendant la phase d'installation décrite dans
le README racine. Ensuite, depuis le dépôt :

```sh
python observability/tests/verify.py
python observability/tests/live.py --profile local-fast
python observability/tests/stale.py --profile local-fast
```

Sur l'hôte Windows préparé, utiliser `.venv/Scripts/python.exe` à la place de
`python`. Le premier programme refuse de télécharger une image absente et exécute
`promtool` sans réseau, avec une racine en lecture seule et un `/tmp` borné.
Le second exige une instance déjà démarrée et vérifie les API Prometheus/Grafana,
les expressions effectivement servies, la datasource, les identités et la
fraîcheur. Il effectue uniquement des lectures, y compris le POST de requête
Grafana. Ces deux premiers contrôles ne provoquent ni arrêt ni transfert.
Le troisième arrête uniquement le relayer du profil choisi, vérifie son absence,
les horodatages conservés et le masquage des mesures courantes, puis le redémarre
et exige le retour à un état prêt. Il est également exécuté par `prove`.

Une capture facultative sous Windows utilise le Chrome ou Edge déjà installé :

```powershell
./observability/tests/capture.ps1 -Profile local-fast -Name grafana-nominal
```

Le navigateur reçoit un profil neuf sous `.local/visual-browser/` et reste en
headless ; aucun profil personnel n'est ouvert. Le nom de capture doit être
nouveau afin de préserver les précédentes. Le PNG et le rapport de commande
restent sous `.local/`. Ils nécessitent une inspection visuelle distincte : un
code de sortie nul ne prouve pas que les panneaux sont lisibles ou corrects.

Les rapports légers par défaut sont `.local/monitoring-checks.json` et
`.local/monitoring-live.json`. Ils doivent être intégrés et hachés par une campagne
de preuves avant publication. Les rapports `.local` restent des artefacts de
travail, conservés tant que l'opérateur ne les supprime pas ; la rétention de la
campagne publiée doit être indiquée dans son manifeste.

Observation initiale du 24 octobre 2026 UTC : `promtool` 3.13.1 a accepté la
configuration et ses 12 règles, puis les huit scénarios de `rules.test.yml`.
Les assertions couvrent nominal, absence de séries, scrape arrêté puis rétabli,
état figé, horloge future, gas faible/attente/pause/intervention/écart d'offre,
réconciliation non concluante puis rétablie et HTTP disponible avec relayer non
prêt. Les tests vérifient aussi qu'un fallback d'indisponibilité ne crée pas une
deuxième série à côté d'un indicateur disponible. Un premier essai de tests avec
racine en lecture seule sans `/tmp` inscriptible a échoué explicitement ; la
commande reproductible fournit désormais ce tmpfs. Ce résultat ne démontre pas
à lui seul un rendu Grafana ni la connexion au relayer.

Le démarrage réel a rendu Prometheus 3.13.1 et Grafana 13.2.4 sains, avec leurs
consultations sur loopback. La datasource Grafana a interrogé Prometheus avec
succès. La vérification nominale initiale est restée en échec pendant le
diagnostic de redémarrage du relayer (`bridge_ready=0`), comme consigné dans
`.local/monitoring-live-datasource.json`.

Les premières captures Chrome headless ont révélé des séries de fallback
dupliquées, des champs de texte vides et un tableau servi obsolète malgré le
fichier modifié. Les requêtes ont été corrigées et le fournisseur est passé de
10 à 30 secondes : la documentation Grafana confirme que seule une valeur
strictement supérieure à 10 force une lecture périodique, utile lorsque les
événements des bind mounts ne remontent pas. Les captures initiales restent des
observations des défauts ; elles ne valident pas les corrections. Les derniers
rapports de campagne font foi pour l'état finalement vérifié.

Après redémarrage coordonné, la vérification nominale du 24 octobre 2026 à
21:26:17 UTC a réussi : 26 contrôles, dont les 22 expressions, la datasource et
les identités 31337/31338 du profil `local-fast`. Le rapport est
`.local/local-fast-monitoring-live.json`. La capture `.local/grafana-final.png`,
produite par Chrome 155.0.8059.41 avec un code de sortie nul, a été inspectée :
les 24 panneaux correspondent à la version corrigée, la disponibilité n'est plus
dupliquée, les blocs de texte sont lisibles et la réconciliation affiche
`balanced`. Les cinq alertes de reprise encore visibles au moment de cette
capture étaient résolues lors de la lecture API à 21:28 UTC. Cette observation
nominale ne remplace pas une capture dédiée de l'état arrêté.

La capture d'arrêt a ensuite révélé la disparition des derniers horodatages
avec les séries instantanées, ainsi que des indications « Indisponible » vertes.
Les trois horodatages et l'âge utilisent désormais `last_over_time(...[24h])` ;
les mesures courantes restent masquées et les valeurs nulles sont grises. Un
neuvième scénario promtool vérifie la conservation après marqueur stale et
l'absence après expiration de la fenêtre. Le premier contrôle de reprise du
test HTTP a aussi été corrigé pour attendre, de façon bornée, la fin du HTTP 502
transitoire de la passerelle au redémarrage. Les rapports finaux distinguent ces
observations des campagnes repassées après correction.

## Seuils et procédures

Les seuils suivants sont des décisions initiales pour les deux profils locaux,
pas des engagements de disponibilité ni des mesures de charge : 15 secondes
avant alerte de service inaccessible, âge d'instantané ou collecte >30 secondes,
retard >5 blocs pendant 30 secondes, attente >120 secondes, gas <0,001 unité
native, réconciliation ancienne >60 secondes. Pause, intervention requise et
écart d'offre déclenchent dès la prochaine évaluation. Les alertes sont visibles
dans Prometheus `/alerts` ; une règle active n'envoie aucun message externe.

### Service indisponible

Vérifier `up{job="bridge"}`, la passerelle de consultation et la santé du relayer.
Consulter les logs JSON bornés et l'état des dépendances avec les commandes du
projet. Relancer seulement les services du profil après correction de la cause.
Ne pas purger les volumes de reprise pour effacer un symptôme.

### Donnees anciennes

Comparer les horodatages UTC au temps de l'hôte, puis vérifier RPC, PostgreSQL et
les checkpoints persistants. Un HTTP 200 et un écran rafraîchi ne suffisent pas.
Ne relever la limite de fraîcheur qu'après justification de la cadence observée.

### Transfert en attente

Lire l'état persistant et les identifiants publics du transfert dans les outils
d'exploitation. Vérifier pause, gas, finalité, nonce et reçu avant toute reprise.
Un timeout ne déclenche pas un mint compensatoire. Une intervention requise doit
être examinée sans réémettre aveuglément une nouvelle transaction.

### Gas de test

Comparer le solde exact RPC au coût maximal configuré avant réapprovisionnement.
Le seuil fixe est indicatif ; sur un Besu local à gas price nul il peut être trop
conservateur. Les faucets concernent le gas des réseaux de test autorisés, pas
automatiquement le token transféré. Ne pas utiliser de fonds réels.

### Pause et reconciliation

Une pause peut être intentionnelle. Identifier l'opérateur, la raison et les
transferts en transit avant sa levée. Lors d'un écart d'offre, conserver les
points de contrôle, transactions et émissions externes, puis appliquer la
procédure d'incident du bridge. Une donnée inconnue ou non concluante n'est pas
un contrôle réussi. Ne pas réparer l'écart par mint automatique.

## Sources primaires

Configuration et évaluation des règles :
[Prometheus, configuration](https://prometheus.io/docs/prometheus/latest/configuration/configuration/),
[règles d'alerte](https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/),
[tests promtool](https://prometheus.io/docs/prometheus/latest/configuration/unit_testing_rules/).
Provisionnement et options des services :
[Grafana, provisioning](https://grafana.com/docs/grafana/latest/administration/provisioning/),
[configuration](https://grafana.com/docs/grafana/latest/setup-grafana/configure-grafana/),
[image Docker](https://grafana.com/docs/grafana/latest/setup-grafana/configure-docker/).
Conservation des valeurs et représentation des absences :
[fonctions temporelles PromQL](https://prometheus.io/docs/prometheus/latest/querying/functions/),
[mappings spéciaux Grafana](https://grafana.com/docs/grafana/latest/visualizations/panels-visualizations/configure-value-mappings/).
Les options réellement acceptées par les images épinglées sont contrôlées par
le démarrage ; les documentations « latest » ne remplacent pas cette exécution.
