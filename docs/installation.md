# Installation et reproduction

## Prérequis

Git, Python 3.12 et Docker Engine Linux avec Compose v2.40 ou compatible, x86-64.
Prévoir une VM avec 6 Gio disponibles pour `local-fast`, 8 Gio pour les deux
profils successivement et 15 Go de disque libres : ce sont des budgets projetés, pas une mesure
de capacité. Le diagnostic initial a aussi révélé une forte pression mémoire
sur l'hôte partagé ; démarrer les profils successivement si nécessaire.
Le CLI de contrôle utilise la bibliothèque standard Python. `bootstrap` crée
un environnement `.venv` avec les dépendances MkDocs verrouillées par hashes,
télécharge les images par digest et prépare des fichiers locaux non versionnés.
Il ne modifie pas les installations globales Python ou .NET.

Utiliser une VM dédiée, un compte de développement et un moteur Docker réservés
au projet. Ne pas y importer de secrets de production. L'accès au moteur donne
des droits étendus : le réserver à l'orchestrateur. Docker Compose ne fournit
pas d'ACL par projet pour l'utilisateur qui possède cet accès.

## Commandes

```text
python scripts/bridge.py doctor
python scripts/bridge.py bootstrap --profile local-fast
python scripts/bridge.py up --profile local-fast
python scripts/bridge.py demo --profile local-fast
python scripts/bridge.py config --profile local-fast
python scripts/bridge.py test --profile local-fast
python scripts/bridge.py scan
python scripts/bridge.py prove --profile local-fast
python scripts/bridge.py docs
python scripts/bridge.py status --profile local-fast
python scripts/bridge.py down --profile local-fast
```

`./scripts/bridge` est le wrapper POSIX, `./scripts/bridge.ps1` celui de PowerShell.
Depuis un clone neuf, commencer par `doctor`, puis `bootstrap`, `up` et `demo`.
`bootstrap` télécharge les versions verrouillées, prépare Solidity, compile les
contrats et construit les images .NET avec restauration NuGet verrouillée. Le
SDK de l'hôte n'est pas nécessaire à ce parcours. `build` reconstruit les images
après un changement applicatif ; cette commande appartient à la phase installation.
Forge reçoit les sources en lecture seule et deux montages d'écriture (`out`,
`cache`). Sur Linux il utilise l'UID/GID non root de l'orchestrateur pour ces
sorties ; le décalage UID1000/UID1001 a été reproduit et corrigé pour les runners.
`test` exécute les tests Python, Solidity et .NET puis le transfert et les pannes.
`prove` ajoute les vérifications de cloisonnement, de persistance et de supervision,
avec un manifeste complet sous `evidence/`. Ces deux commandes modifient les
chaînes **de test** et peuvent interrompre temporairement les services du profil.
Pour produire une campagne, un commit source doit déjà exister. Le code testé est
commité **avant** l'ajout du manifeste de preuves, afin d'éviter une référence
circulaire. Un arbre modifié est admis si son empreinte exacte est conservée ;
les changements pendant une campagne font échouer le contrôle des sources.

`doctor --offline` omet les sondes HTTP de phase installation. Le diagnostic
détecte outils, ressources, moteur et capacités réelles du processus enfant
avec un fichier témoin hors dépôt. Il ne lit aucun fichier personnel existant.

`up` ne télécharge pas d'image et ne construit pas de service applicatif. S'il
manque un digest local, lancer `bootstrap` dans la phase installation. Les
chaînes refusent les chain IDs ou clients attendus absents. Aucun paramètre RPC
arbitraire n'est accepté dans cette interface. Le déploiement lie chain ID,
genesis, bytecodes, paire de contrats et rôles attendus. Un déploiement interrompu
laisse `deployment-in-progress.json` et bloque une répétition aveugle : examiner
les reçus et le journal avant une reprise manuelle.

## Profils et données

Les Anvil minent à la demande. `demo` et les scénarios produisent explicitement
les confirmations locales requises après vérification du reçu canonique.
Un envoi direct avec un autre outil ne fait pas avancer trois blocs à lui seul.
Sans activité, la hauteur reste stable ; cela ne signifie pas que le RPC est
indisponible. Les relayers continuent leurs contrôles. Chaque Anvil dispose
d'un plafond de 1 Gio, justifié par la reprise mesurée des instantanés de
l'[incident du 27 octobre](adr/0006-arrets-prolonges.md).

Besu utilise le lanceur officiel `besu-untuned` de la version verrouillée,
sans activation implicite de JFR. Son healthcheck vérifie le RPC et le chain ID
31339 ; la progression des blocs est observée séparément par le relayer.

| Profil | RPC A / B | Documentation | Statut JSON | Grafana / Prometheus |
|---|---|---|---|---|
| local-fast (31337/31338) | 18545 / 28545 | 18080 | 18082/status | 13000 / 18090 |
| local-besu (31339/31340) | 38545 / 48545 | 18081 | 18083/status | 13001 / 18091 |
| integration-testnet | désactivé | aucune | aucun | aucun |

Tous ces ports utilisent `http://127.0.0.1:`. Le tableau Grafana se trouve sous
`/d/t3l4n-bridge/` et le suivi projet historique sous `/status/` du site documentaire.
`docs` reconstruit le site ; appeler ensuite `status --profile ...` pour son
instantané. Le site est commun aux profils : le dernier `status` indique
explicitement le profil observé. Les deux API JSON et les Grafana restent séparés.

Les projets Docker portent `t3l4n-bridge-local-fast` et `t3l4n-bridge-local-besu`.
Les volumes restent présents après `down`. L'expérience de persistance arrête
et recrée les conteneurs du profil choisi, sans supprimer les volumes. Les
fichiers sous `.local/runtime/<profil>/r2` sont propres au profil et exclus de Git.
Ils contiennent les clés de test générées et la configuration publique. Conserver
ensemble ces fichiers et les volumes pour reprendre une instance ; ne pas restaurer
une base plus récente que ses chaînes sans réconciliation. Les anciennes données
`r1` ont été conservées ; aucune migration implicite ni suppression n'est effectuée.

Les sous-réseaux Docker du projet sont des /28 dans `10.231.240.0/24` (local-fast)
et `10.231.241.0/24` (local-besu). Ils évitent l'épuisement du pool de /16 observé
sur le moteur partagé initial. Vérifier les conflits de routes ou VPN avec
`doctor` avant d'adapter ces plages dans une autre VM ; un chevauchement détecté
par Docker doit rester un échec explicite, sans nettoyage de réseaux tiers.

Pour local-besu, `bootstrap` génère une clé de nœud locale et un genesis QBFT à
un validateur. La configuration de génération est versionnée, les clés ne le
sont pas. Les identités diffèrent entre installations ; conserver le genesis
et son hash public pour reproduire exactement une instance. Un opérateur local
aléatoire reçoit du gas de test au genesis ; il déploie les contrats et finance
les comptes d'exécution et de pause. Cette signature ponctuelle ne donne pas au
relayer la clé administrateur. Le genesis public figure dans les preuves Besu.

Les comptes de développement publics Anvil restent exclusivement sur les
chaînes locales. L'option quiet supprime leur affichage de démarrage.
Les clés des exécuteurs sont générées séparément. Les secrets restent des fichiers
locaux montés seulement où nécessaires ; cette solution n'est pas un HSM. Les ACL
Windows de l'hôte doivent être vérifiées par son administrateur avant tout accès partagé.

## Limites appliquées

La configuration générée et conservée dans `deployment.json` est la référence :
18 decimals, 1 000 tokens par transfert, plafond de mint de 100 000 tokens par
époque de 3 600 secondes, gas 350 000 et prix au plus 100 gwei pour le relayer,
12 tentatives, délai RPC de 5 secondes. Les soumissions sont limitées à 10 par
minute et par destination ; le signataire applique aussi sa propre limite en mémoire.
Les transactions d'administration utilisent un budget distinct, borné par l'outil
local. Ces limites ne suppriment pas les pouvoirs d'un administrateur compromis.

Anvil conserve l'historique avec `--preserve-historical-states` et un instantané
toutes les 10 secondes. L'expérience de 520 blocs et deux arrêts propres ne prouve
pas une durabilité après coupure brutale ; une limite d'historique a été observée à
4 100 blocs. Voir [ADR-0005](adr/0005-persistance-anvil.md).

## Arrêt et nettoyage

`down` cible uniquement le nom Compose fixe du profil, avec délai de 20 secondes.
Aucun `docker system prune`, nettoyage global, suppression de volume ou
suppression récursive de fichiers n'est implémenté. Un effacement des données
doit être explicite, limité aux noms de ce projet et précédé d'un inventaire.
