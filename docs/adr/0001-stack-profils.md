# ADR-0001 — stack bornée et trois profils

Date initiale et mise à jour : 2026-10-24. Statut : décision appliquée au
démonstrateur local ; validation par environnement dans [les résultats](../resultats.md).

## Exigence

Environnement reproductible et compartimenté, sans service payant ni Kubernetes,
avec séparation du véritable TELA et des simulations.

## Décision initiale

Retenir Docker Compose, deux Anvil pour local-fast, puis Besu QBFT
mono-validateur et Anvil pour local-besu. Le validateur unique limite les
ressources du test de compatibilité ; il ne fournit pas de tolérance byzantine
et ne permet aucune conclusion sur le consensus TELA. Son identité est générée
au bootstrap ; genesis non secret, hash et versions doivent accompagner chaque
campagne. integration-testnet reste désactivé sans paramètres vérifiés.

Choisir PostgreSQL 17 pour ses transactions et verrous, MkDocs pour les documents
et Python pour l'orchestration et les preuves. Retenir Solidity/OpenZeppelin,
Foundry et .NET/Nethereum pour les composants métier. La séparation des services
et une VM dédiée sont préférées à l'ajout d'un orchestrateur plus complexe.

Au jalon 1, Foundry 1.3.1 servait aussi de runtime Anvil ; les dépendances
applicatives et la supervision étaient des choix à implémenter. Cette description
historique ne représente plus leur état courant.

## Mise en œuvre observée

| Composant | Choix effectif et ancrage dans le dépôt |
|---|---|
| Compilation et tests Solidity | Forge/Foundry 1.3.1, solc 0.8.30, OpenZeppelin 5.4.0 vendored avec révision et SHA-256 |
| Nœuds Anvil | Image distincte 1.8.4 et états historiques conservés ; décision et expériences dans [ADR-0005](0005-persistance-anvil.md) |
| Cible EVM | London explicite, sans supposer PUSH0 ou Cancun ; Besu local active London dans son genesis |
| Besu local | 26.10.0, QBFT mono-validateur, image dérivée pour le répertoire de données et le chargement JNI |
| Relayer, signataire, opérateur ponctuel | .NET 10 LTS ; SDK 10.0.402, runtime 10.0.13 ; exécutables séparés |
| Clients applicatifs | Nethereum.Web3 / Nethereum.Signer 6.1.0, Npgsql 10.0.3, Newtonsoft.Json 13.0.4 |
| Persistance | PostgreSQL 17.11 ; schéma applicatif et comptes distincts de l'administrateur |
| Supervision | Prometheus 3.13.1 et Grafana 13.2.4, configurations et tableaux dans `observability/` |
| Documentation | MkDocs 1.6.1, dépendances transitives et hashes verrouillés |

Les images de `sandbox/versions.lock.json` sont épinglées par digest et
plateforme linux/amd64. Les images applicatives construites sont identifiées
par leur ID et reliées aux sources ; un ancien build est refusé. Les artefacts
Solidity sont reliés au rapport de compilation par leurs empreintes exactes.
Un hash de sources courantes ne suffit pas à attribuer ces sources à un ancien
bytecode.

Les projets .NET existent, sont compilés et possèdent leurs `packages.lock.json`.
Les builds utilisent `restore --locked-mode` et l'audit NuGet transitif.
La première restauration avait retenu Newtonsoft.Json 11.0.2 et signalé NU1903 ;
la référence explicite 13.0.4 a corrigé ce résultat. Le contrôle exécuté après
correction n'a pas remonté cet avertissement ; il ne garantit pas l'absence de
toute vulnérabilité future. Le SDK initial de l'hôte ne correspondait pas au
verrou : les versions explicitement préparées et les conteneurs remplacent
cette hypothèse initiale, sans changer silencieusement `global.json`.

Nethereum 6.1.0 a été conservé pour éviter une migration majeure non nécessaire.
PostgreSQL 17.11 fournit les primitives utilisées ; une autre majeure n'apportait
pas de besoin démontré. Besu 26.10.0 avait été retenu à partir de ses notes de
correctifs ; le changement de fork Hoodi de 26.10.1 n'était pas nécessaire à ce
réseau privé. Le choix d'Anvil a ensuite changé pour une raison expérimentale et
un correctif identifié, comme consigné dans ADR-0005.

## Conséquences, vérification et limites

L'installation utilise le réseau ; l'exécution emploie les images locales avec
`--pull never`. Les tests de contrats et .NET disposent de chemins hors réseau.
Les restrictions effectives restent celles mesurées sur le moteur, pas celles
déduites du YAML ou d'une liste déclarative de destinations.

Les critères d'acceptation sont compilation London, tests sans skip, lecture
historique après reprise, transferts, cloisonnement et supervision réellement
exercés. Leurs preuves sont CONTRACT-001, SIGN-001, RELAYER-001, TRANSFER-001,
BESU-PROTO-001 et OBS-001 dans le [registre](../claims.yaml).

Aucun changement de versions ne conserve automatiquement les validations
précédentes. La VM dédiée reste à fournir sur l'hôte partagé ; les conteneurs
ne confinent pas Codex ou l'administrateur Docker. Les sources officielles et
les choix de versions figurent dans [sources](../sources.md). La présence d'une
image ou un audit de dépendances ne vaut ni certification ni recette d'un
réseau partagé.
