# Clés, menaces et frontières

## Exigences et portée

Aucun mainnet ni actif réel ; seuls les profils locaux explicitement autorisés
sont exécutables. Les paramètres du véritable TELA ne sont pas déduits d'un
Besu local. Les [informations manquantes](informations-manquantes.md) empêchent
l'intégration partagée. Les affirmations de sécurité concernent le code et les
expériences nommées : ISO-001, ISO-002, KEY-001, SIGN-001, CONTRACT-001.

Les processus Codex et le moteur Docker disposent de droits hôtes étendus.
Leur accès n'est pas limité à ce projet par les réseaux Compose. La machine/VM
dédiée reste à fournir (ENV-01) ; les témoins de cloisonnement ne démontrent pas
cette frontière absente.

## Signature et permissions

Les clés `key_a` et `key_b` sont générées pour ce laboratoire, conservées dans
`.local/runtime/<profil>/r2/` et montées seulement dans le service signataire.
Le relayer reçoit un jeton de service et le mot de passe PostgreSQL applicatif,
mais aucune clé privée. Un opérateur ponctuel signe les administrations Besu avec
une clé séparée. Les comptes publics d'Anvil servent seulement à cette simulation locale.

`ITransactionSignerBackend` permet de remplacer le mécanisme de signature.
`FileKeySigner` charge aujourd'hui un fichier local : ce n'est ni un HSM, ni un
coffre matériel, ni une preuve d'effacement des copies mémoire ou sauvegardes.
Le signataire ne contacte aucun RPC et ne vérifie donc pas la réalité d'un burn.

`POST /sign` exige `X-Bridge-Token` ; une comparaison d'empreintes à temps constant
protège la comparaison du secret. Le JSON est borné et ses champs strictement
contrôlés. Seuls les domaines configurés, la méthode `completeTransfer`,
la paire, le destinataire non nul, le montant, le nonce et les limites de gas
acceptés peuvent être signés. La valeur native est zéro. Les erreurs sont bornées :
401 pour authentification invalide, 400 pour requête invalide, 403 pour politique
refusée, 429 pour fréquence, 500 pour échec interne. Les payloads signés sont
renvoyés au relayer et persistés avant diffusion ; ils ne sont pas des artefacts
à publier dans les rapports.

Le compte SQL `bridge_app` est distinct de `sandbox_admin`. Le bootstrap
administrateur crée son schéma ; le relayer y utilise ses tables et verrous.
L'application n'est pas superutilisatrice. Les administrateurs PostgreSQL et
hôte peuvent toutefois lire la base et ses transactions signées.

## Limites appliquées par le code

Valeurs du déploiement local courant ; les paramètres réellement exécutés sont
dans le fichier de déploiement et le manifeste de campagne.

| Contrôle | Valeur / portée |
|---|---|
| Token | 18 decimals, implémentation dédiée sans rebase ni frais |
| Montant par transfert | 1 000 tokens, soit `10^21` unités minimales |
| Mint par époque | 100 000 tokens par période fixe de 3 600 secondes, par bridge destination |
| Gas de completion | 350 000 ; borne absolue de configuration/signature 500 000 |
| Prix du gas | Maximum 100 gwei par défaut ; attente au-delà du plafond |
| Fréquence | 10 tentatives par minute et destination dans PostgreSQL ; 10 signatures par minute et chaîne dans le processus signataire |
| Tentatives | 12 par défaut ; réconciliation d'un envoi ambigu avant arrêt définitif |
| RPC | Timeout de 5 secondes par défaut, sans redirection ni proxy implicite du client .NET |
| Transaction pending | Intervention après 300 secondes par défaut, sans remplacement automatique de frais |
| Requête signataire | Corps au plus 4 096 octets ; champs et encodage vérifiés |

La fenêtre de mint est fixe : deux périodes adjacentes peuvent autoriser un
cumul supérieur au plafond d'une période sur une fenêtre glissante.
Le limiteur du signataire est en mémoire et repart au redémarrage ; le suivi
des tentatives du relayer est persistant. Ces contrôles ne suppriment pas les
pouvoirs des clés et administrateurs. Les montants sont calculés en entiers.

## Compartimentage des services

Compose impose utilisateurs non root, racines en lecture seule, suppression des
capacités Linux, `no-new-privileges`, volumes explicites, limites CPU/RAM/PID et
journaux tournants. Aucun service n'obtient socket Docker, répertoire personnel
ou identifiants de production. Les consultations sont liées à `127.0.0.1`.

Besu charge une bibliothèque JNI pour RocksDB : le tmpfs `/jni-tmp` autorise
cette exécution avec propriétaire et permissions restreints. `/tmp` et la
racine conservent leurs restrictions ; le conteneur n'est pas privilégié.

Les secrets Compose hors Swarm restent des fichiers montés de l'hôte. Le
répertoire runtime est restreint sous Unix ; les fichiers lisibles du conteneur
n'offrent aucun chiffrement de coffre. Sous Windows, ces modes ne remplacent
pas une ACL NTFS vérifiée. Les flux HTTP internes de signature et PostgreSQL
sans TLS sont des choix du laboratoire local ; ils ne doivent pas être
transposés tels quels à un réseau partagé.

Les tests témoins comparent un accès autorisé et le même accès interdit, puis
l'accès à un fichier inoffensif monté ou absent. Les tests applicatifs vérifient
la distribution des secrets et le refus de signature sans authentification.
Une déclaration Compose réussie ne vaut pas résultat runtime ; consulter
[les preuves](tests-preuves.md).

L'installation des dépendances est une phase réseau distincte. La liste
`sandbox/egress-policy.json` décrit les destinations prévues mais ne constitue
pas un pare-feu hôte. Les réseaux internes et l'absence de masquerading ne
garantissent pas un filtrage fin des ports, de DNS ou des accès spéciaux à l'hôte
Docker Desktop. L'administrateur du moteur peut contourner les compartiments.

## Menaces et conséquences

| Compromission / défaut | Conséquence et protection partielle |
|---|---|
| Clé d'exécution | Mints frauduleux possibles sur la paire dans les plafonds ; pause et révocation limitent les effets futurs |
| Relayer ou jeton de signature | Requêtes frauduleuses compatibles avec la politique ; le signataire ne dispose pas d'une preuve du burn |
| Administrateur du bridge | Attribution/révocation de rôles et levée de pause ; la paire déjà fixée reste immuable |
| Administrateur du token | Attribution de `BRIDGE_ROLE` et émissions externes contournant les plafonds du bridge |
| RPC incohérent ou malveillant | Arrêt sur incohérence détectée ; des réponses mensongères cohérentes restent dans la frontière de confiance |
| Base perdue ou modifiée | Perte/falsification des données de reprise ; contraintes et réconciliation ne remplacent pas sauvegarde et contrôle d'accès |
| Hôte ou moteur compromis | Accès possible aux clés, volumes et processus ; frontières Compose insuffisantes |
| Finalité locale invalidée | Un effet déjà crédité peut exiger une intervention ; aucune compensation automatique n'efface ce risque |

Un test inclut volontairement un mint forgé par un exécuteur autorisé : il
démontre ce pouvoir, pas une propriété de preuve interchaîne. Des attestations
multiples, une vérification cryptographique de preuves ou un autre mécanisme
de garde sont des options futures, non implémentées.

Gitleaks complète la revue avec sept témoins synthétiques éphémères : deux motifs
GitHub et cinq motifs génériques, y compris dans les champs d'empreintes.
Les exceptions restent ciblées sur des empreintes publiques exactes de fichiers,
d'une définition d'affirmation et du runtime ERC20 relu sur les deux profils.
Le rapport brut de reprise nomme ce dernier hash `token` ; seule sa valeur
publique exacte est admise, et un témoin aléatoire dans ce champ reste détecté.
Seul le champ `tokenAddress` accepte une adresse hexadécimale de 20 octets, dans
les rapports JSON de preuves ; une clé Ethereum de 32 octets ne correspond pas.
Aucun répertoire de preuves n'est exclu. Les autres règles restent actives, même
sur ces champs. Un scan réussi
ne démontre pas l'absence de toute catégorie de secret.

Le scan complet dispose de cinq minutes, contre une minute pour les témoins.
Cette limite a été révisée après une expiration de la CI sur environ 52 Mo de
preuves ; les ressources du conteneur restent bornées à un CPU et 256 Mio.
Un timeout reste un échec de vérification. Le conteneur porte un nom unique et
un label de projet ; son nettoyage après interruption vise uniquement ce nom,
avant suppression de la copie montée. Aucun nettoyage global Docker n'est utilisé.
