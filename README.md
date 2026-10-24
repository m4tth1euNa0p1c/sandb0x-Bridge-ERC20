# T3l4N-Bridge-ERC20

Sandbox de test pour préparer un bridge ERC20 bidirectionnel entre un EVM
représentant TELA et Ethereum Sepolia. **Jalon 1 : infrastructure et preuves de
démarrage. Aucun transfert ERC20 ni relayer n'est encore implémenté.**

Les résultats exécutés, les limites et le commit testé sont dans
[le rapport](docs/resultats.md), [le registre](docs/claims.yaml) et `evidence/`.
Un Besu local est une simulation technique ; il ne permet pas de déduire la
configuration du véritable TELA. L'intégration réelle est désactivée.

## Démarrage local

Prérequis : Git, Python 3.12, Docker Engine Linux avec Compose v2.40 ou compatible,
architecture x86-64, accès HTTPS pour l'installation. Budget indicatif : 2 Gio de
RAM disponibles pour local-fast, 4 Gio pour local-besu, 5 Gio de disque. Une VM
dédiée est requise pour la frontière hôte visée ; la première expérience sur un
Docker Desktop partagé ne l'établit pas.

```powershell
git clone https://github.com/m4tth1euNa0p1c/T3l4N-Bridge-ERC20.git
cd T3l4N-Bridge-ERC20
git switch codex/bridge-sandbox-evidence
python scripts/bridge.py doctor
python scripts/bridge.py bootstrap --profile local-fast
python scripts/bridge.py up --profile local-fast
python scripts/bridge.py test
python scripts/bridge.py prove --profile local-fast
python scripts/bridge.py docs
python scripts/bridge.py status
python scripts/bridge.py down
```

La branche doit être disponible dans le clone : les commits de cette livraison
sont locaux tant qu'ils n'ont pas été poussés. Sous POSIX, `./scripts/bridge`
est l'interface équivalente ; sous PowerShell, `./scripts/bridge.ps1` est aussi fourni.
`bootstrap` télécharge et prépare ; `up` exige les images déjà présentes et ne
télécharge rien. `prove` arrête puis redémarre **ce projet** pour tester sa
persistance. `down` conserve les volumes et les fichiers de test locaux.

Documentation : **http://127.0.0.1:18080/** lorsque local-fast est démarré.
Tableau : **http://127.0.0.1:18080/status/**, instantané horodaté à régénérer avec
`status`. Ce tableau ne prétend pas suivre un bridge fonctionnel en direct.
Les mêmes vues sont sur le port 18081 pour local-besu.

Pour Besu : remplacer le profil par `local-besu` dans `bootstrap`, `up`, `prove`
et `down`. La validation de sa configuration et son exécution sont deux résultats
distincts dans le rapport. `up --profile integration-testnet` échoue explicitement.

## Contenu et méthode

- [Règles du dépôt](AGENTS.md), [exigences](docs/exigences.md), [journal](docs/journal.md).
- [Décisions](docs/adr/0001-stack-profils.md), [installation détaillée](docs/installation.md).
- [50 agents et 50 skills](docs/agents.md), spécialisés et maintenus sur retours observés.
- [Prérequis TELA/Sepolia](docs/informations-manquantes.md), [limites](docs/limites.md).

Boucle de travail : exigence → choix → code → test → preuve → documentation.
Les jalons 2 à 5 restent à livrer : protocole, reprise, pannes, compatibilité
applicative Besu, supervision métier et intégration testnet.
