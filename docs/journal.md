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
