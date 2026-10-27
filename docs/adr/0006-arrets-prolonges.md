# ADR-0006 — blocs Anvil à la demande et lanceur Besu

Date : 2026-10-27. Statut : décision retenue, portée de validation dans
[les résultats](../resultats.md). Complète [ADR-0005](0005-persistance-anvil.md).

**Exigences.** Ressources bornées, reprise vérifiée, résultats conservés et
supervision honnête. Un démarrage réussi n'établit pas un fonctionnement
continu pendant plusieurs jours.

**Observation conservée.** Au diagnostic du 27 octobre, les quatre nœuds
étaient arrêtés depuis le 25 octobre. Docker indique `OOMKilled=true` pour
les trois Anvil limités à 384 Mio. Deux instantanés sont des JSON complets
de 206 501 857 et 230 588 596 octets ; le troisième est tronqué à
196 440 064 octets. Besu s'est arrêté avec code 1 et `OOMKilled=false`,
sans erreur terminale dans ses journaux disponibles. Les relayers signalent
`ready=false` ; Grafana masque les valeurs métier courantes et affiche les
alertes. Voir `evidence/incident-20261027/initial-observation.json` et
`preservation.json`, référencés depuis les résultats.

**Analyse Anvil.** Le [code du build testé](https://github.com/foundry-rs/foundry/blob/50af4efe189dc64bad2b75ed6990b835de66c4ae/crates/anvil/src/eth/backend/mem/storage.rs)
conserve les blocs et clone les structures lors de la sauvegarde. Limiter
les états historiques ne limite donc pas tous les coûts. Avec un bloc toutes
les deux secondes, l'instance accumule des blocs même sans transfert.
L'allocation exacte responsable de l'OOM n'a pas été mesurée pendant l'incident.
`--transaction-block-keeper` supprimerait des transactions et reçus nécessaires
à la réconciliation ; cette option n'est pas retenue. `--mixed-mining` conserve
le timer et ne corrige pas la croissance au repos.

**Décision Anvil.** Utiliser l'automine, sans timer permanent. Les helpers
locaux confirment explicitement un reçu canonique en produisant au plus la
profondeur configurée, actuellement trois blocs supplémentaires. Ils vérifient
le profil, l'identité et le reçu avant et après. Le relayer ne mine aucun bloc.
Le scénario de réorganisation suspend explicitement cette avance pour rester
avant la finalité conventionnelle. Une transaction envoyée directement au RPC
peut donc rester en attente de confirmations jusqu'à une avance volontaire.

La limite Anvil est portée à 1 Gio pour permettre de tester la reprise des
instantanés existants sur copies. Ce plafond est une décision de ressources,
pas une garantie de capacité illimitée. L'activité réelle fait toujours croître
les blocs ; surveiller mémoire, taille des sauvegardes et ancienneté des états.
L'arrêt propre reste explicite. Aucun reset, aucune purge de reçus et aucune
réduction silencieuse de la rétention ne sont introduits.

**Analyse Besu.** Le [lanceur officiel de la version 26.10.0](https://github.com/besu-eth/besu/blob/26.10.0/build.gradle)
active Java Flight Recorder. L'enregistrement et les bibliothèques natives
partagent ici `/jni-tmp`, limité à 128 Mio. Le code OpenJDK
[interrompt la JVM sur certains échecs d'écriture JFR](https://github.com/openjdk/jdk25u/blob/master/src/hotspot/share/jfr/writers/jfrStreamWriterHost.inline.hpp).
Une saturation témoin reproduit la sortie 1 sans OOM et, lorsque les logs JFR
sont activés, le message de manque d'espace. Le contenu du tmpfs réel ayant
disparu à l'arrêt, sa saturation le 25 octobre demeure une hypothèse étayée,
pas une observation rétrospective.

**Décision Besu.** Utiliser `besu-untuned`, fourni dans la même image verrouillée,
avec les limites Java déjà explicites. Ce lanceur n'active pas automatiquement
JFR. Le tmpfs JNI exécutable reste limité et réservé à l'utilisateur du nœud.
Un healthcheck HTTP JSON-RPC vérifie le chain ID local attendu ; l'ancien
healthcheck hérité vérifiait seulement l'existence d'un fichier PID.

**Reprise de l'incident.** Préserver d'abord instantanés et bases hors Git avec
SHA-256. Une réparation structurelle du seul instantané tronqué peut produire
un candidat en gardant les champs complets et les entrées historiques complètes.
Elle ne vaut pas validation métier. Tester les copies isolées, puis vérifier
identités, bytecodes, reçus source et destination, `processed`, nonces persistés,
checkpoints et offre avant toute reprise. Ne jamais fabriquer un mint pour
compenser une lecture absente. La procédure et ses résultats restent dans le
dossier de cet incident ; aucune récupération automatique générale n'est ajoutée.

**Validation et limites.** Le témoin Anvil compare une période d'inactivité
mesurée avec et sans timer, puis conserve les contrôles de 520 blocs et deux
reprises. Les campagnes complètes vérifient ensuite les deux profils avec les
sources exactes. Les affirmations ANVIL-001, DB-001, RESILIENCE-001 et
BESU-PROTO-001 restent limitées à ces scénarios ; elles n'établissent ni haute
disponibilité, ni durabilité après coupure hôte, ni comportement du véritable TELA.
