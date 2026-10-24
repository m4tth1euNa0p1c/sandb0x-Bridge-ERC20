# Contrat des métriques du relayer local

Implémentation : `src/Bridge.Relayer/RelayerService.cs`, méthode `Metrics()`.
Exposition HTTP : `/metrics`, texte Prometheus `version=0.0.4`. Chaque scrape
lit un instantané ; un HTTP 200 n'établit pas que cet instantané soit récent.
La politique de fraîcheur est donc indépendante de la disponibilité HTTP.

| Métrique | Type / labels bornés | Sens |
|---|---|---|
| bridge_ready | gauge 0/1 | Instantané prêt et non périmé selon le relayer |
| bridge_status_updated_timestamp_seconds | gauge | Heure Unix UTC du dernier instantané |
| bridge_code_info | info / version, profile | Version injectée au démarrage et profil réellement chargé |
| bridge_network_info | info / network, chain_id | Réseaux validés au cycle ; absents avant validation |
| bridge_last_collection_timestamp_seconds | gauge / network | Dernière collecte réussie ; 0 si aucune |
| bridge_finalized_lag_blocks | gauge / network | max(0, frontière de finalité − prochain bloc à lire + 1) |
| bridge_chain_head | gauge / network | Tête lue |
| bridge_chain_finalized | gauge / network | Frontière selon la politique configurée ; pas une affirmation de finalité TELA |
| bridge_gas_balance_wei | gauge / network | Gas natif du compte de signature dédié, en wei |
| bridge_paused | gauge 0/1 / network | Pause du bridge lue on-chain |
| bridge_transfers | gauge / state | Nombre de lignes par état persistant |
| bridge_oldest_pending_seconds | gauge | Âge du plus ancien transfert non final, ou 0 si aucun |
| bridge_attempts_pending | gauge | Somme des tentatives des transferts non finaux ; peut décroître |
| bridge_cycle_errors_total | counter / component | Erreurs de cycle, remise à zéro au redémarrage |
| bridge_reconciliation_state | gauge 0/1 / state | Une seule des quatre catégories vaut 1 |
| bridge_reconciliation_updated_timestamp_seconds | gauge | Heure du contrôle d'offre |

`network` appartient à `{a,b}`. Les douze états de transfert sont `observed`,
`waiting_finality`, `source_finalized`, `destination_prepared`,
`destination_submitted`, `destination_finalized`, `waiting_gas`, `waiting_pause`,
`waiting_rate`, `retryable_failure`, `rejected`, `intervention_required`.
Les catégories de réconciliation sont `balanced`, `mismatch`, `inconclusive`,
`unavailable`. Les composants d'erreur sont `identity`, `collector`, `processor`,
`reconciliation`, `database`, `status`.

Prometheus ajoute `job` et `instance`. La règle `bridge:telemetry_fresh` vaut 1
seulement si le scrape réussit et si l'instantané a moins de 30 secondes, avec
une tolérance d'horloge future de 5 secondes. Une série absente reste absente ;
les panneaux de disponibilité la traduisent explicitement en indisponibilité.
Les seuils sont des décisions locales, pas une mesure de disponibilité garantie.

Les nombres Prometheus sont des flottants : un solde en wei peut perdre ses
derniers chiffres. Les contrôles comptables exacts utilisent les entiers du
relayer, de PostgreSQL et des contrats, jamais les valeurs du dashboard.
`bridge_code_info` décrit le code exécuté ; il ne prouve pas qu'une campagne a
validé cette version. Cette validation appartient au registre des affirmations
et aux manifestes de preuves.

Aucun transfert, hash de transaction, adresse utilisateur ou message d'erreur
libre n'est un label. La version change uniquement lors d'un déploiement et la
rétention locale limite les anciennes séries. Les logs JSON peuvent corréler un
transfert avec ses hashes publics ; les clés, mots de passe, jetons et bytes
de transaction signée ne doivent pas être journalisés.
