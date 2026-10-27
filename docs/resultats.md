# Résultats vérifiés et limites

**27 octobre 2026 — nouvelle validation en cours.** Les campagnes du 25 octobre
ci-dessous restent historiques. L'incident d'arrêt des nœuds, les diagnostics
et la reprise sont conservés dans `evidence/incident-20261027/`. Le correctif
modifie les sources ; les affirmations précédentes sont obsolètes jusqu'aux
nouvelles campagnes complètes. Les relayers ont repris après audit explicite,
sans modification des transferts, observations, nonces ni tentatives.

Le démonstrateur local exécute les transferts burn/mint dans les deux sens,
avec persistance, signature séparée, tests de panne et supervision. Les deux
campagnes ci-dessous ont réussi sur les mêmes sources figées. Elles ne valident
ni Sepolia ni le véritable TELA. La frontière d’une VM dédiée reste à établir.

Commit **du code testé** : `b97c541fd7cb64a85560ba693742a62304c84885`.
Empreinte exacte : `8ef4e51a3dae091b530d29993fbdeef919431286264bb4e50d34f083258aec2e`.
Les rapports sont ajoutés dans un commit ultérieur. Les fichiers de compte rendu
et `evidence/` sont exclus explicitement de cette empreinte pour éviter un cycle.
Les autres fichiers, les définitions d’affirmations, commandes, codes de sortie,
versions et images sont conservés dans chaque manifeste.

| Profil | Hôte d’exécution | Campagne UTC | Contrôles | Preuve |
|---|---|---|---|---|
| local-fast | Windows 11 / Docker Desktop Linux | 2026-10-25T00:24:52Z → 2026-10-25T00:32:48Z | 18/18 | <a href="../evidence/20261025T002452Z-local-fast/manifest.json">Manifeste et empreinte</a> |
| local-besu | Windows 11 / Docker Desktop Linux | 2026-10-25T00:33:58Z → 2026-10-25T00:40:29Z | 18/18 | <a href="../evidence/20261025T003358Z-local-besu/manifest.json">Manifeste et empreinte</a> |

## Résultats mesurés

- 72 tests Python réussis ; aucun test ignoré.
- 27 tests Solidity réussis, dont fuzzing et invariants ; artefacts London empreintés.
- 64 tests signataire et 51 tests relayer réussis sans réseau, sans skip.
- Un aller-retour réel de 10 tokens sur chaque profil, avec 18 decimals, montants
  entiers, reçus, identifiants et destinataires conservés dans les rapports.
- local-fast : neuf scénarios réussis, incluant relecture, pause, RPC suspendu,
  gas nul, concurrence de deux processus, crashs 91/92 et réorganisation avant finalité.
- local-besu : sept scénarios réussis ; gas forcé à zéro et réorganisation Anvil
  restent explicitement **non exécutés**, sans validation Besu de ces deux cas.
- Quatorze services inspectés par profil ; contrôles positifs et négatifs de
  réseau, fichiers et secrets réussis. Cela ne confine pas l’administrateur hôte.
- Redémarrage propre avec SQL, transferts, identités et progression conservés.
  Aucun test de coupure brutale de l’hôte n’est assimilé à ce résultat.
- Anvil 1.8.4 : 520 blocs et deux reprises propres dans le témoin historique.
- Supervision : 12 règles, neuf scénarios promtool/51 assertions, arrêt réel du
  relayer et restauration, puis 26 contrôles API/requêtes sur chaque profil.
- MkDocs strict, scan Gitleaks et ses six témoins positifs réussis.
- 50 définitions d’agents et 50 skills : contrôle structurel réussi. Leur présence
  ne signifie pas 50 processus actifs ni 50 évaluations comportementales complètes.

Les 28 affirmations du [registre](claims.yaml) comprennent 26 validations locales
ou Besu local et deux blocages (hôte dédié et TELA). Leur état est recalculé si
sources, définition ou artefact changent. Les tests avec doubles RPC et stockage
restent distincts des expériences PostgreSQL/RPC réelles.

## Jalons

| Jalon | Résultat | Limite restante |
|---|---|---|
|1 — environnement, décisions et profils|Exécuté et documenté|Hôte initial partagé|
|2 — aller-retour et persistance|Démontré sur les deux profils locaux|Confiance dans le relayer autorisé|
|3 — pannes, invariants, cloisonnement|Scénarios locaux et tests de contrats passés|Portée bornée des injections|
|4 — Besu, supervision et documentation|Compatibilité Besu 26.10.0/London/QBFT local et vues observées|QBFT mono-validateur sans tolérance byzantine|
|5 — Sepolia puis TELA de test|Non exécuté, profil désactivé|Identités, accès, droits, clés et gas de test manquants|

La [CI GitHub Actions](https://github.com/m4tth1euNa0p1c/T3l4N-Bridge-ERC20/actions/runs/40146594435) sur `b97c541fd7cb64a85560ba693742a62304c84885` est `success`.
Cette CI comprend l’installation depuis un clone neuf et 18 contrôles local-fast.
Sa <a href="../evidence/20261025T002725Z-local-fast/manifest.json">campagne complète</a>
et l’<a href="../evidence/ci-b97c541/index.json">empreinte de l’archive téléchargée</a>
sont conservées. Les sources de la CI et des campagnes locales ont les mêmes octets.
Le job d’intégration réelle reste ignoré explicitement. Les artefacts Actions
ont une rétention de 30 jours ; les rapports copiés dans ce dépôt durent tant que
le dépôt est conservé. Les captures et expériences complémentaires sont indexées
dans <a href="../evidence/visual-20261024/index.json">les rendus</a> et
<a href="../evidence/diagnostics-20261024/index.json">les diagnostics historiques</a>.

## Échecs conservés et corrections

Les preuves J1 restent historiques. Les incidents IPAM, passerelle, JNI Besu,
droits SQL, dépendance JSON vulnérable, mutex .NET, association de reçus entre
chaînes et historique Anvil sont décrits dans [le journal](journal.md).
Les neuf premières injections local-fast ont passé mais leur campagne était
invalide car les sources avaient changé. Un premier essai Besu a rencontré
WinError10013 ; le suivant a réussi sans changement de pare-feu ni de paramètres OS.

La CI sur clone neuf a révélé un UID Forge incompatible avec les fichiers du
runner Linux. Le témoin UID 1000/UID 1001 reproduit le refus puis la réussite ; les
sources sont désormais montées en lecture seule et seules les sorties écrites.
Des hashes publics de code et adresses ERC20 ont également déclenché le scan :
les exceptions restent ciblées et les six témoins de détection repassent.
Le tableau arrêté a été corrigé pour conserver l’heure connue et ne pas afficher
en vert les valeurs indisponibles. Chaque campagne finale rejoue ces contrôles.

La contre-vérification du point d’entrée a ensuite révélé que `build` et `test`
avec `integration-testnet` pouvaient commencer des tâches locales avant le refus.
La garde a été remontée à l’entrée des sept commandes d’exécution. Les tests
avec sentinelles et les sept invocations CLI réelles confirment désormais un
refus avant processus enfant ou RPC. Les profils locaux restent acceptés.
Les rôles et skills CI et crash intègrent ces retours ; les anciennes campagnes
sur `fd030c4` restent historiques et ne valident pas le nouveau code.

La CI du commit de rapports `b394413` a ensuite atteint le timeout de 60 secondes
du scan, sur environ 52 Mo de preuves : 17 contrôles réussis et un échec global
conservé dans <a href="../evidence/ci-b394413-failed/index.json">son index</a>.
Le budget du scan complet est désormais borné à cinq minutes ; CPU, mémoire,
absence de réseau, lecture seule et périmètre des fichiers restent inchangés.
Le scanner porte un nom unique et son conteneur est retiré après timeout ou
interruption, avant suppression de sa copie. Un témoin réel à deux secondes
a vérifié le refus 124 et ce nettoyage ciblé, avant et après commit du correctif.
Trois régressions Python et un sixième témoin de détection couvrent ce retour.
Les <a href="../evidence/scanner-timeout-20261025/index.json">procédures,
résultats et empreintes</a> restent conservés. Les nouvelles campagnes complètes
et la CI ci-dessus valident les sources corrigées ; le timeout ancien n’est
jamais requalifié en succès.

Après une interruption de session, Docker Desktop était arrêté. Une campagne
locale a échoué explicitement sur le moteur absent. Au redémarrage, une ancienne
transaction finalisée de l’instance Anvil avait perdu son reçu et son effet :
bloc destination remplacé, burn source conservé, nonce réservé encore libre.
Le relayer a demandé une intervention et rendu la réconciliation inconclusive.
La cause de l’arrêt du moteur n’a pas été déterminée.

Une intervention opérateur limitée à cet identifiant a revérifié le contexte,
puis permis au processeur existant de rediffuser la transaction déjà persistée.
Les 22 contrôles réussissent : **même signature, nonce et hash**, un seul crédit
exact et une offre équilibrée. Aucune signature nouvelle ni compensation
automatique n’a été produite. Les <a href="../evidence/restart-incident-20261024/index.json">observations,
la procédure exécutée et les résultats</a> restent conservés. La campagne
local-fast sur cet hôte a ensuite été rejouée entièrement.

Une relance a également refusé le verrou laissé par la campagne interrompue.
Après vérification de l’absence de processus actif, ce seul verrou a été archivé
et retiré ; données et six résultats partiels ont été conservés. Le manifeste
de cette relance reste en échec. Les campagnes finales n’effacent aucun échec.

## Limites et reproduction

Aucun débit soutenu, percentile de latence ni engagement de disponibilité n’a
été mesuré. Les horodatages donnent des durées de campagne, pas un benchmark.
L’historique Anvil a échoué à 4 100 blocs dans une expérience distincte ; ses
instantanés périodiques ne constituent pas un journal durable après coupure.
Le relayer autorisé peut frauder dans ses pouvoirs ; les administrateurs peuvent
attribuer les rôles du token. Les plafonds et la pause ne prouvent pas le burn distant.

Les [prérequis manquants](informations-manquantes.md) restent requis avant tout
réseau partagé. Les faucets concernent le gas, pas automatiquement le token ERC20.
Consulter [installation](installation.md) et [exploitation](exploitation.md) pour
`bootstrap`, `up`, `demo`, `test`, `prove`, `docs`, `status` et `down`.
Le suivi projet sous `/status/` est un instantané UTC ; Grafana et les API locales
nécessitent les services démarrés. Leur fonctionnement continu dépend de l’hôte.

Le <a href="../evidence/finalization-b97c541/delivery.json">contrôle de livraison</a>
conserve l’état observé des deux relayers, les huit pages servies et le registre
effectif. Son <a href="../evidence/finalization-b97c541/delivery-index.json">index</a>
référence les commandes, la procédure et la capture relue. Ce relevé reste
une observation historique horodatée.
