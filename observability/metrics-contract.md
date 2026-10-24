# Contrat de supervision — proposé, non implémenté au J1

| Métrique proposée | Type / labels bornés | Attendu |
|---|---|---|
| bridge_last_collection_success_timestamp_seconds | gauge / chain, direction | Dernière collecte réelle |
| bridge_finalized_lag_blocks | gauge / chain | Écart par rapport au bloc finalisé selon la politique configurée |
| bridge_pending_transfers | gauge / state, direction | Nombre d'états non terminaux |
| bridge_oldest_pending_seconds | gauge / direction | Ancienneté réelle, pas un compteur nul fictif |
| bridge_retries_total | counter / reason parmi enum | Nombre de tentatives |
| bridge_rpc_errors_total | counter / chain, category enum | Classe d'erreur, sans URL secrète |
| bridge_test_gas_balance_wei | gauge / chain, role enum | Solde de gas des comptes dédiés |
| bridge_reconciliation_ok | gauge / pair | 1 si point de contrôle cohérent, 0 si écart ; absent si inconnu |
| bridge_paused | gauge / chain | État on-chain lu |
| bridge_build_info | info / commit, version | Version réellement exécutée |

Ne pas utiliser transfer_id, transaction_hash, adresse utilisateur ou message
d'erreur libre comme label. Les logs JSON pourront contenir transfer_id,
state_from, state_to, chain_id, block_hash, tx_hash et catégorie d'erreur, sans clé,
mot de passe, credential RPC ou transaction signée en clair.

Alertes futures : collecte obsolète, retard croissant, transit trop ancien,
solde gas sous seuil, écart d'offre, pause, service absent. Afficher absence de
scrape et date des données, plutôt qu'un tableau vert avec série absente.
