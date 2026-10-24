# Agents spécialisés du projet

Cette bibliothèque contient **50 définitions d'agents** pour T3l4N-Bridge-ERC20.
Les fichiers sont dans `.codex/agents/` ; les procédures associées sont les
skills `.agents/skills/bridge-<sujet>/SKILL.md`. Leur présence ne signifie pas
que 50 processus travaillent simultanément.

## Format et activation

Chaque fichier autonome définit `name`, `description` et
`developer_instructions`. Aucun modèle ni privilège supplémentaire n'est imposé.
Ce format et le dossier de projet suivent la
[documentation officielle des sous-agents Codex](https://learn.chatgpt.com/docs/agent-configuration/subagents).
Les agents héritent des permissions du parent. La consigne « lecture seule »
d'un rôle de revue est une instruction de travail ; elle n'est pas une nouvelle
frontière de sécurité.

Le catalogue est livré avec le dépôt pour être disponible dans les sessions
qui chargent ses définitions. Le chargement des 50 rôles par l'interface de la
session courante n'a pas été démontré par le seul contrôle TOML. Si un rôle
n'apparaît pas dans les agents proposés, recharger la session et vérifier les
capacités de l'installation avant d'annoncer son activation.

Les skills de dépôt suivent l'emplacement de découverte
[`.agents/skills` documenté par OpenAI](https://learn.chatgpt.com/docs/build-skills).
Une validation de leur frontmatter et une évaluation de leur comportement sont
deux vérifications distinctes.

## Utilisation

Attribuer une mission courte, des fichiers possédés, un résultat attendu et
un environnement. Par exemple : « Confie à `bridge_cloisonnement` le contrôle
des frontières de `local-fast`, avec des témoins non sensibles et un rapport
des commandes exécutées ; ne modifie pas les autres compartiments. »

N'activer que les rôles utiles au travail en cours, dans la limite de concurrence
de la session. Un agent producteur et un agent de revue peuvent se compléter ;
deux agents ne doivent pas modifier les mêmes fichiers sans coordination.
L'exécution du bridge reste séparée de l'orchestration des agents.

Les rôles ont accompagné l'implémentation des contrats, du relayer, de la
signature et des tests de panne. Les preuves de ces composants sont les rapports
d'exécution, distincts de la validation structurelle du catalogue. Trois agents
spécialisés ont travaillé dans la session, dans la limite des quatre places
simultanées incluant l'orchestrateur ; les cinquante définitions restent réutilisables.

## Catalogue

Pour un sujet `besu-qbft`, le fichier est
`.codex/agents/bridge-besu-qbft.toml`, le nom d'appel est
`bridge_besu_qbft` et le skill est
`.agents/skills/bridge-besu-qbft/SKILL.md`. Cette règle vaut pour toutes les lignes.

| Agent | Mission distincte | Mode |
|---|---|---|
| `bridge_architecture` | Concevoir ou réviser un choix d'architecture T3l4N et ses frontières de confiance. | Production sur fichiers attribués |
| `bridge_exigences` | Transformer une demande du projet en critères observables et détecter les exigences non couvertes. | Production sur fichiers attribués |
| `bridge_menaces` | Examiner les risques du bridge et les pouvoirs des identités techniques. | Revue en lecture seule |
| `bridge_sources` | Vérifier une affirmation technique ou une version auprès d'une source officielle. | Production sur fichiers attribués |
| `bridge_versions` | Choisir et épingler les versions du démonstrateur et analyser leur compatibilité. | Production sur fichiers attribués |
| `bridge_doctor` | Diagnostiquer la capacité réelle de l'hôte à exécuter la sandbox. | Production sur fichiers attribués |
| `bridge_compose` | Implémenter ou corriger les services et profils Docker Compose du projet. | Production sur fichiers attribués |
| `bridge_anvil` | Construire des expériences Anvil reproductibles pour les deux réseaux simulés. | Production sur fichiers attribués |
| `bridge_besu_qbft` | Configurer et vérifier un réseau Besu local avec consensus explicitement documenté. | Production sur fichiers attribués |
| `bridge_tela_identite` | Établir les prérequis et l'identité d'un environnement TELA de test fourni par son opérateur. | Revue en lecture seule |
| `bridge_sepolia_identite` | Vérifier un RPC Sepolia autorisé et les prérequis d'intégration de test. | Revue en lecture seule |
| `bridge_reseaux` | Concevoir les communications minimales entre compartiments et leurs destinations autorisées. | Production sur fichiers attribués |
| `bridge_cloisonnement` | Démontrer des frontières précises avec des ressources témoins non sensibles. | Production sur fichiers attribués |
| `bridge_secrets` | Détecter les expositions de clés, jetons et données sensibles dans le périmètre publiable. | Revue en lecture seule |
| `bridge_signature` | Implémenter l'interface de signature remplaçable et son isolement. | Production sur fichiers attribués |
| `bridge_erc20` | Implémenter les tokens dédiés au démonstrateur et examiner leurs interfaces burn/mint. | Production sur fichiers attribués |
| `bridge_burn_mint` | Implémenter le flux source burn+événement et destination traitement+mint atomiques. | Production sur fichiers attribués |
| `bridge_transfer_id` | Concevoir et tester la séparation de domaine des identifiants de transfert. | Production sur fichiers attribués |
| `bridge_roles` | Vérifier la séparation administration, pause et exécution et les chemins d'attribution. | Revue en lecture seule |
| `bridge_pause` | Implémenter et tester les mécanismes de pause sans perdre la trace des transferts. | Production sur fichiers attribués |
| `bridge_plafonds` | Implémenter les limites de montant, gas, fréquence et tentatives prévues par la politique. | Production sur fichiers attribués |
| `bridge_decimals` | Garantir les conversions de montants et le rejet des paires non prises en charge. | Production sur fichiers attribués |
| `bridge_fuzz` | Écrire et exécuter du fuzzing utile sur les contrats de bridge. | Production sur fichiers attribués |
| `bridge_invariants` | Définir et éprouver les invariants globaux du bridge sous séquences adverses. | Production sur fichiers attribués |
| `bridge_deploiement` | Produire des déploiements reproductibles sur un profil explicitement autorisé. | Production sur fichiers attribués |
| `bridge_collecte` | Implémenter une collecte RPC historique complète et réessayable. | Production sur fichiers attribués |
| `bridge_finalite` | Examiner les politiques de finalité par réseau et les réponses RPC requises. | Revue en lecture seule |
| `bridge_reorg` | Implémenter la détection et le traitement des réorganisations source. | Production sur fichiers attribués |
| `bridge_checkpoints` | Implémenter une progression de collecte résistant aux interruptions. | Production sur fichiers attribués |
| `bridge_dedup` | Implémenter la déduplication des observations et l'unicité de l'effet métier. | Production sur fichiers attribués |
| `bridge_postgres_schema` | Concevoir le schéma PostgreSQL des événements, transferts et tentatives. | Production sur fichiers attribués |
| `bridge_migrations` | Écrire et vérifier des migrations reproductibles conservant les états de reprise. | Production sur fichiers attribués |
| `bridge_concurrence` | Implémenter la répartition sûre des transferts entre workers concurrents. | Production sur fichiers attribués |
| `bridge_nonces` | Implémenter la réservation persistante des nonces par compte et chaîne. | Production sur fichiers attribués |
| `bridge_soumission` | Implémenter l'envoi de transactions destination malgré les réponses RPC ambiguës. | Production sur fichiers attribués |
| `bridge_recus` | Implémenter l'analyse des reçus et la finalisation destination. | Production sur fichiers attribués |
| `bridge_retry` | Implémenter des réessais bornés selon la classe d'erreur. | Production sur fichiers attribués |
| `bridge_crash` | Tester les fenêtres de panne entre persistance, signature, envoi et reçu. | Production sur fichiers attribués |
| `bridge_rpc_pannes` | Construire des scénarios RPC indisponible, lent ou contradictoire. | Production sur fichiers attribués |
| `bridge_reconciliation` | Implémenter la réconciliation bidirectionnelle de l'offre et des montants en transit. | Production sur fichiers attribués |
| `bridge_metriques` | Instrumenter les services sans cardinalité non bornée. | Production sur fichiers attribués |
| `bridge_alertes` | Définir et tester les alertes pour les incidents du bridge. | Production sur fichiers attribués |
| `bridge_grafana` | Construire les tableaux Grafana à partir des métriques réellement disponibles. | Production sur fichiers attribués |
| `bridge_logs` | Implémenter des logs exploitables et corrélés sans fuite de secret. | Production sur fichiers attribués |
| `bridge_etat_projet` | Construire la vue projet reliant code exécuté, campagnes et affirmations. | Production sur fichiers attribués |
| `bridge_registre_preuves` | Maintenir les affirmations techniques et leurs statuts calculables. | Production sur fichiers attribués |
| `bridge_manifestes` | Produire et contrôler les manifestes exacts des expériences exécutées. | Production sur fichiers attribués |
| `bridge_documentation` | Rédiger et corriger la documentation à partir du code et des expériences présents. | Production sur fichiers attribués |
| `bridge_ci` | Implémenter la CI reproductible du périmètre réellement livré. | Production sur fichiers attribués |
| `bridge_amelioration` | Améliorer les instructions du projet à partir d'échecs ou ambiguïtés réellement observés. | Production sur fichiers attribués |

## Amélioration fondée sur des observations

La demande d'amélioration continue est appliquée pendant les travaux autorisés,
à partir de défauts observés. Elle ne crée ni tâche perpétuelle, ni service
automatique restant actif après la session.

1. Conserver un cas concret : demande reçue, version de l'agent/skill, artefacts
   d'entrée, action observée, résultat attendu et conséquence de l'écart.
2. Reproduire le cas dans un périmètre local adapté. Séparer un défaut
   d'instruction d'un bug applicatif, d'une information manquante ou d'un outil absent.
3. Modifier le rôle ou le skill responsable au point le plus étroit ; éviter
   d'ajouter la même règle aux 50 fichiers. Mettre à jour les références si le
   code ou les commandes ont changé.
4. Vérifier le format, puis rejouer le cas et un cas voisin qui doit rester
   accepté. Pour un changement risqué, une évaluation indépendante doit recevoir
   la demande et les artefacts bruts, sans la réponse attendue.
5. Conserver le résultat dans une campagne de preuves et résumer dans le
   [journal](journal.md) la cause, le changement et ses limites. Mettre à jour
   l'affirmation concernée ; ne pas promouvoir une preuve ancienne après modification.

Le rôle `bridge_amelioration` coordonne une révision ciblée quand il est sollicité.
Il ne déclenche pas de publication, de push, de création illimitée d'agents ou
de modification des permissions. Le nombre de fichiers ne mesure pas leur qualité.

## Vérification initiale

Le 24 octobre 2026, un contrôle Python 3.12 avec `tomllib` a analysé les
50 fichiers `bridge-*.toml`. Résultat observé : **50/50 analysés**, 50 noms
uniques, uniquement les trois champs requis, correspondance entre nom et fichier,
et référence vers le skill de même sujet. Code de sortie : **0**.

Les empreintes exactes de la version livrée sont recalculées dans la campagne
du jalon 1 par `scripts/validate_capabilities.py` et l'inventaire des sources.

Ce contrôle établit la structure des définitions. Il ne démontre ni leur
chargement par une interface, ni la compétence effective des 50 rôles sur des
missions réelles. L'évaluation comportementale se fait lors d'usages documentés,
puis nourrit les corrections ci-dessus.
