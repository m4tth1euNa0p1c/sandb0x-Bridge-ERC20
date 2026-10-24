# ADR-0001 — stack bornée et trois profils

Date : 2026-10-24. Statut : accepté pour l'infrastructure du jalon 1 ; dépendances
applicatives candidates à revalider avant leur première utilisation.

**Exigence.** Environnement reproductible et compartimenté, sans service payant ni
Kubernetes, avec séparation du véritable TELA et des simulations.

**Décision.** Docker Compose, deux Anvil pour local-fast ; Besu QBFT local avec
un validateur et Anvil pour local-besu. L'unique validateur réduit la charge du
test de compatibilité. Il ne fournit pas de tolérance byzantine. Son identité est
générée au bootstrap, conservée localement ; le genesis non secret et son hash
doivent être conservés par campagne. Cela ne suppose aucun consensus pour TELA.

PostgreSQL 17 plutôt qu'une nouvelle majeure : primitives transactionnelles et
verrouillages adaptés à la reprise ; correctif 17.11 épinglé. MkDocs 1.6.1 avec
dépendances transitives et hashes verrouillés. Python 3.12 ne sert qu'à
l'orchestration multiplateforme et aux preuves, pas au relayer.

Foundry 1.3.1 est retenu pour la simulation Anvil à cible London et ses commandes
stables de persistance. Sa présence ne signifie pas qu'il s'agit de la version
la plus récente ou qu'une revue de sécurité complète a été réalisée. Avant le
jalon 2, revoir ses correctifs et ceux de solc 0.8.30 / OpenZeppelin 5.4.0 ; tout
changement requiert une nouvelle campagne. `evm_version=london` évite de supposer
PUSH0, Cancun ou des opcodes plus récents sur le Besu local configuré avec
`londonBlock=0`. La compatibilité du bytecode du bridge reste à démontrer.

Besu 26.10.0 est épinglé : la note officielle annonce des correctifs de sécurité.
26.10.1 porte sur la programmation d'un fork Hoodi, sans besoin pour ce réseau
QBFT local. Ce choix ne valide aucun déploiement sur un réseau partagé.

Relayer envisagé : .NET 10 LTS, SDK 10.0.402 et runtime 10.0.13 ; .NET 8/9 se
rapprochent de leur fin de support. Nethereum.Web3 6.1.0 évite une migration
automatique vers la majeure 7 ; les dépendances transitives seront verrouillées
lors de la création du projet .NET. Le SDK présent sur l'hôte est 10.0.401 : il
ne satisfait pas `global.json`. Aucun build .NET n'est revendiqué.

Prometheus 3.13.1 (branche LTS) et Grafana 13.2.4 sont épinglés pour le jalon 4,
sans démarrage de ces services au jalon 1. La matrice métrique est une spécification.

**Conséquences.** Installation en réseau sur l'hôte, puis exécution locale avec
`--pull never` et réseaux internes. La liste des destinations n'est pas un
pare-feu. Images verrouillées par digest d'index et plateforme linux/amd64 ; les
IDs d'images locaux sont conservés en preuve. Les choix et sources officielles
sont détaillés dans [sources](../sources.md).

**Limite.** L'hôte initial est partagé et non confiné par Codex. Migrer vers une
VM dédiée avant d'ajouter des accès TELA ou Sepolia. Les tests de conteneurs ne
valident pas cette frontière hôte.
