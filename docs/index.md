# Objectif et état réel

Ce dépôt construit une sandbox ERC20 burn/mint bidirectionnelle avec tokens
dédiés, relayer autorisé, PostgreSQL et signature séparée. Le démonstrateur est
réservé aux tests. Il ne prouve pas cryptographiquement un burn distant et
n'est associé à aucune certification réglementaire.

## Implémentation présente

Les contrats Solidity, tests Forge, signataire, relayer .NET, schéma PostgreSQL,
profils Compose, supervision Prometheus/Grafana et scénarios de panne sont
présents. Les tests isolés ont été exécutés ; l'état final des transferts entre
nœuds, de la reprise et de la compatibilité Besu dépend des campagnes scellées.

Lire [les résultats](resultats.md) pour les nombres, environnements, commandes et
limites réellement observés. Le [registre](claims.yaml) relie chaque affirmation
à son code et sa procédure. Les statuts proposés ou implémentés ne valent pas
vérification ; les preuves devenues obsolètes sont signalées.

| Environnement | Ce qu'il représente |
|---|---|
| local-fast | Deux Anvil distincts pour protocole et injections de panne |
| local-besu | Une simulation Besu QBFT locale et une seconde chaîne locale |
| integration-testnet | Sepolia et véritable TELA de test, actuellement désactivés |

Aucun paramètre TELA n'est déduit de Besu local. Les accès, permissions, tokens et
fonds de test externes figurent dans [les informations manquantes](informations-manquantes.md).
La VM dédiée reste à fournir sur l'hôte initial partagé.

## Utiliser et vérifier

Le [guide d'installation](installation.md) décrit les prérequis et la séparation
installation/exécution. L'[architecture](architecture.md) expose rôles et reprise ;
les [tests](tests-preuves.md) décrivent les assertions ; les
[procédures d'exploitation](exploitation.md) donnent adresses et actions d'incident.

Le [tableau projet](status/index.md) est un instantané daté actualisé par
`python scripts/bridge.py status`. L'exploitation utilise Grafana :
[local-fast](http://127.0.0.1:13000/d/t3l4n-bridge) ou
[local-besu](http://127.0.0.1:13001/d/t3l4n-bridge), lorsque les services sont actifs.
Toujours lire l'horodatage et les indicateurs d'indisponibilité.

Le [journal](journal.md) conserve décisions et expériences ; le
[catalogue](agents.md) décrit les 50 agents et 50 skills. Leur présence ne
démontre pas 50 compétences indépendamment évaluées et n'assure pas une activité
autonome permanente. La disponibilité dépend de l'hôte et du démarrage explicite.
