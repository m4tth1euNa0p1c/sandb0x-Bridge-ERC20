# ADR-0005 — états historiques et sauvegarde Anvil

Date : 2026-10-24. Statut : accepté après expériences isolées ; intégration et
version vérifiée référencées dans [les résultats](../resultats.md).

L'[ADR-0006](0006-arrets-prolonges.md) complète cette décision après les arrêts
observés le 27 octobre : automine sans timer, confirmations explicites et
diagnostic de sauvegarde interrompue. Les résultats ci-dessous restent historiques.

**Exigence.** La collecte historique doit vérifier le nonce source et la
réconciliation doit lire l'offre à des blocs explicites, y compris après reprise.

**Observations.** Deux redémarrages propres d'Anvil 1.3.1 ont conservé les
transactions, reçus et logs du témoin, mais les lectures d'état historique ont
échoué avec `BlockOutOfRangeError`. L'option `--preserve-historical-states`
a permis de réussir ces mêmes contrôles. Une fenêtre de 520 blocs et deux
redémarrages a ensuite été testée sur 1.3.1 et 1.8.4 avec succès. Ces expériences
ne démontrent ni un archivage illimité ni la résistance à une coupure de l'hôte.

L'absence apparente de reçus du déploiement courant provenait d'une mauvaise
association entre chaînes ayant les mêmes adresses de contrats. Cette erreur
de l'orchestrateur a été corrigée ; elle n'est pas attribuée à Anvil.

**Décision.** Les nœuds utilisent Anvil **1.8.4** avec conservation des états
historiques et cible London. Cette première version stable après la
[correction #17148](https://github.com/foundry-rs/foundry/pull/17148) ajoute un
verrou de minage lors de la capture de l'état, pour éviter une incohérence entre
la base et les métadonnées. Les [notes officielles 1.8.4](https://github.com/foundry-rs/foundry/releases/tag/v1.8.4)
mentionnent ce correctif. La compilation et les tests Solidity restent sur
Foundry 1.3.1 et solc 0.8.30, déjà vérifiés ; les deux images sont distinctes.

**Migration du laboratoire.** L'option ne reconstruit pas les états historiques
absents. La révision locale `r2` utilise de nouveaux volumes et de nouveaux
fichiers de test sous `.local/runtime/<profil>/r2`. Les volumes et fichiers des
expériences précédentes sont conservés. Aucun burn utilisateur n'avait été
exécuté dans l'instance précédente : seules les transactions de déploiement
existaient. Cette migration de données synthétiques ne constitue pas une
procédure de migration d'actifs réels.

**Limites.** Les sauvegardes périodiques ne sont pas un journal transactionnel
durable. Une coupure brutale peut revenir avant la dernière sauvegarde, même
si trois blocs supplémentaires étaient visibles. Les preuves de reprise de
nœuds couvrent un arrêt propre. Les crashs du relayer sont des tests distincts.
Les historiques Anvil restent bornés ; un état ancien absent doit faire échouer
le traitement, sans repli silencieux vers `latest`.

**Borne mesurée.** Sur 1.8.4, le contrôle de 520 blocs vides et deux reprises
réussit. Après 4 100 blocs vides, les appels d'état aux blocs 1, 2 et 3 échouent
déjà avant l'arrêt, alors que transactions, reçus, logs, code courant et hash des
blocs restent disponibles. Ce résultat en échec est conservé comme mesure de
limite, pas comme validation. Il n'autorise aucune durée universelle de reprise :
à deux secondes par bloc, la fenêtre dépend aussi des transactions et des états.
