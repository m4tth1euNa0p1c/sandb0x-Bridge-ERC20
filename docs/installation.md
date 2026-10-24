# Installation et reproduction

## Prérequis

Git, Python 3.12 et Docker Engine Linux avec Compose v2.40 ou compatible, x86-64.
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
python scripts/bridge.py config --profile local-fast
python scripts/bridge.py test
python scripts/bridge.py scan
python scripts/bridge.py prove --profile local-fast
python scripts/bridge.py docs
python scripts/bridge.py status
python scripts/bridge.py down --profile local-fast
```

`./scripts/bridge` est le wrapper POSIX, `./scripts/bridge.ps1` celui de PowerShell.
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
arbitraire n'est accepté dans cette interface au jalon 1.

## Profils et données

| Profil | RPC A | RPC B | Documentation | Portée |
|---|---|---|---|---|
| local-fast | 127.0.0.1:18545 | 127.0.0.1:28545 | 127.0.0.1:18080 | Deux Anvil, 31337/31338 |
| local-besu | 127.0.0.1:38545 | 127.0.0.1:48545 | 127.0.0.1:18081 | Besu QBFT + Anvil, 31339/31340 |
| integration-testnet | désactivé | désactivé | aucune | Paramètres TELA inconnus |

Les projets Docker portent `t3l4n-bridge-local-fast` et `t3l4n-bridge-local-besu`.
Les volumes restent présents après `down`. L'expérience de persistance arrête
et recrée les conteneurs du profil choisi, sans supprimer les volumes. Les
fichiers sous `.local/runtime/<profil>` sont propres au profil et exclus de Git.

Les sous-réseaux Docker du projet sont des /28 dans `10.231.240.0/24` (local-fast)
et `10.231.241.0/24` (local-besu). Ils évitent l'épuisement du pool de /16 observé
sur le moteur partagé initial. Vérifier les conflits de routes ou VPN avec
`doctor` avant d'adapter ces plages dans une autre VM ; un chevauchement détecté
par Docker doit rester un échec explicite, sans nettoyage de réseaux tiers.

Pour local-besu, `bootstrap` génère une clé de nœud locale et un genesis QBFT à
un validateur. La configuration de génération est versionnée, les clés ne le
sont pas. Les identités diffèrent entre installations ; conserver le genesis
et son hash public pour reproduire exactement une instance. L'offre de gas du
genesis est vide au jalon 1 ; aucun transfert de test Besu n'est revendiqué.

Les comptes de développement publics Anvil restent exclusivement sur les
chaînes locales. L'option quiet supprime leur affichage de démarrage.

## Arrêt et nettoyage

`down` cible uniquement le nom Compose fixe du profil, avec délai de 20 secondes.
Aucun `docker system prune`, nettoyage global, suppression de volume ou
suppression récursive de fichiers n'est implémenté. Un effacement des données
doit être explicite, limité aux noms de ce projet et précédé d'un inventaire.
