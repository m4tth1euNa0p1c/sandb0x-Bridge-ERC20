# T3l4N-Bridge-ERC20

Sandbox de test pour un bridge ERC20 bidirectionnel entre un EVM représentant
TELA et Ethereum Sepolia. Les contrats, le relayer PostgreSQL, le signataire
séparé et la supervision sont implémentés. Des transferts aller-retour ont été
exécutés sur les profils Anvil/Anvil et Besu/Anvil. **La portée validée dépend
du commit et des campagnes référencés dans le rapport, pas de la présence du code.**

Les résultats exécutés, les limites et le commit testé sont dans
[le rapport](docs/resultats.md), [le registre](docs/claims.yaml) et `evidence/`.
Un Besu local est une simulation technique ; il ne permet pas de déduire la
configuration du véritable TELA. L'intégration réelle est désactivée.

## Démarrage local

Prérequis : Git, Python 3.12, Docker Engine Linux avec Compose v2.40 ou compatible,
architecture x86-64, accès HTTPS pour l'installation. Budget indicatif, non
benchmarké : 6 Gio de RAM libres pour installation et local-fast, 8 Gio pour
local-besu, 15 Gio de disque pour images et artefacts. Une VM
dédiée est requise pour la frontière hôte visée ; la première expérience sur un
Docker Desktop partagé ne l'établit pas.

```powershell
git clone https://github.com/m4tth1euNa0p1c/T3l4N-Bridge-ERC20.git
cd T3l4N-Bridge-ERC20
git switch codex/bridge-sandbox-evidence
python scripts/bridge.py doctor
python scripts/bridge.py bootstrap --profile local-fast
python scripts/bridge.py up --profile local-fast
python scripts/bridge.py demo --profile local-fast
python scripts/bridge.py test
python scripts/bridge.py prove --profile local-fast
python scripts/bridge.py docs
python scripts/bridge.py status
python scripts/bridge.py down
```

La branche dédiée est poussée périodiquement, sans fusion vers main.
Sous POSIX, `./scripts/bridge`
est l'interface équivalente ; sous PowerShell, `./scripts/bridge.ps1` est aussi fourni.
`bootstrap` installe les dépendances, compile et prépare les images ; `up`
exige ces images, déploie une paire de tokens de test au premier démarrage et
vérifie les identités avant d'activer les services. `build` reconstruit les images
après modification du code .NET. `test` et `prove` exécutent des transferts et des
injections de panne locales. `prove` arrête puis redémarre **ce projet** pour
tester sa persistance. `down` conserve les volumes et les fichiers de test locaux.

Documentation : **http://127.0.0.1:18080/** lorsque local-fast est démarré.
Tableau : **http://127.0.0.1:18080/status/**, instantané horodaté à régénérer avec
`status`. Les mêmes vues sont sur le port 18081 pour local-besu.
Supervision interrogée par Grafana : **http://127.0.0.1:13000/d/t3l4n-bridge/**
(13001 pour local-besu). État courant du relayer : **http://127.0.0.1:18082/status**
(18083 pour local-besu). Une valeur ancienne ou indisponible doit rester visible.

Pour Besu : remplacer le profil par `local-besu` dans `bootstrap`, `up`, `prove`
et `down`. La validation de sa configuration et son exécution sont deux résultats
distincts dans le rapport. `up --profile integration-testnet` échoue explicitement.

## Contenu et méthode

- [Règles du dépôt](AGENTS.md), [exigences](docs/exigences.md), [journal](docs/journal.md).
- [Décisions](docs/adr/0001-stack-profils.md), [installation détaillée](docs/installation.md).
- [50 agents et 50 skills](docs/agents.md), spécialisés et maintenus sur retours observés.
- [Prérequis TELA/Sepolia](docs/informations-manquantes.md), [limites](docs/limites.md).

Boucle de travail : exigence → choix → code → test → preuve → documentation.
Le [journal](docs/journal.md) distingue les incidents corrigés et les vérifications
restantes. Les intégrations Sepolia et TELA restent désactivées jusqu'à obtention
des identités, accès, permissions et fonds de test. La nouvelle instance `r2`
conserve les états historiques Anvil ; les données des essais antérieurs sont
préservées, voir [ADR-0005](docs/adr/0005-persistance-anvil.md).
