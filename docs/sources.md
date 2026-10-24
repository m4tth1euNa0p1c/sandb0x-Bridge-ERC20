# Sources officielles et décisions

Consultation : 2026-10-24. Les références justifient une décision ou une API ;
elles ne prouvent pas que notre code a passé un test. Les digests sont résolus
au registre d'images et conservés dans `sandbox/versions.lock.json`.

| Sujet | Source primaire | Usage et limite |
|---|---|---|
| .NET LTS | [Politique Microsoft](https://dotnet.microsoft.com/en-us/platform/support/policy/dotnet-core), [métadonnées 10.0](https://dotnetcli.blob.core.windows.net/dotnet/release-metadata/10.0/releases.json) | .NET 10 LTS, SDK 10.0.402 / runtime 10.0.13 retenus ; pas de build .NET J1 |
| Nethereum | [Installation officielle](https://docs.nethereum.com/docs/getting-started/installation/), [6.1.0](https://github.com/Nethereum/Nethereum/releases/tag/6.1.0) | Base candidate pour le relayer ; pas de restauration transitive J1 |
| Foundry | [Release v1.3.1](https://github.com/foundry-rs/foundry/releases/tag/v1.3.1) | Anvil épinglé et commande `--help` réellement interrogée dans l'image |
| Solidity | [Compiler / cible EVM](https://docs.soliditylang.org/en/latest/using-the-compiler.html), [0.8.30](https://github.com/argotorg/solidity/releases/tag/v0.8.30) | London explicite, aucun bytecode métier compilé J1 |
| OpenZeppelin | [Documentation 5.x](https://docs.openzeppelin.com/contracts/5.x), [release 5.4.0](https://github.com/OpenZeppelin/openzeppelin-contracts/releases/tag/v5.4.0) | Interfaces de token/rôles à implémenter ; pas d'assimilation de la bibliothèque au bridge |
| Besu | [QBFT](https://github.com/besu-eth/besu-docs/blob/main/docs/private-networks/tutorials/qbft.md), [releases](https://github.com/besu-eth/besu/releases) | Configuration reproductible de test ; mono-validateur sans tolérance byzantine |
| PostgreSQL | [Versioning](https://www.postgresql.org/support/versioning/), [17.11](https://www.postgresql.org/docs/17/) | Majeure 17 et correctif épinglé |
| Docker | [Réseaux internes](https://docs.docker.com/reference/compose-file/networks/), [services](https://docs.docker.com/reference/compose-file/services/), [secrets](https://docs.docker.com/reference/compose-file/secrets/) | Configuration et limites ; les tests runtime déterminent le résultat local |
| Prometheus | [Cycle LTS](https://prometheus.io/docs/introduction/release-cycle/) | Branche 3.13 retenue, métriques métier futures |
| Grafana | [13.2.4](https://github.com/grafana/grafana/releases/tag/v13.2.4) | Image future épinglée, aucune recette J1 |
| MkDocs | [Notes 1.6.1](https://www.mkdocs.org/about/release-notes/) | Build strict dans un venv verrouillé |
| Gitleaks | [Configuration v8.30.1](https://github.com/gitleaks/gitleaks/blob/v8.30.1/README.md) | Règles par défaut, exception ciblée sur une empreinte publique et contrôle positif |
| Réseaux Ethereum | [Documentation Ethereum](https://ethereum.org/developers/docs/networks/) | Séparation testnets/local ; pas de RPC Sepolia interrogé |
| Agents Codex | [Agents spécialisés](https://learn.chatgpt.com/docs/agent-configuration/subagents) | Définitions TOML de projet héritant des permissions |
| Skills Codex | [Skills de dépôt](https://learn.chatgpt.com/docs/build-skills) | Répertoire `.agents/skills`, découverte et descriptions ciblées |

Les accès HTTPS hôtes aux registres et sources sont des observations, pas une
allowlist imposée. L'API GitHub sans authentification a renvoyé HTTP 403 ; le
clone Git authentifié et les consultations web ont fonctionné. Ne pas copier
des tokens dans des URLs pour contourner cet échec.
