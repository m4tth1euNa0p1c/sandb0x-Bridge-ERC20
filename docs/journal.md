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
