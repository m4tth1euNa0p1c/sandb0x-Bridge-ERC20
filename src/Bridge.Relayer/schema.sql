-- The operator bootstrap creates schema bridge with bridge_app as owner.
-- The application intentionally has no CREATE privilege on the database.
CREATE TABLE IF NOT EXISTS bridge.networks (
 chain_id bigint PRIMARY KEY, identity_hash text NOT NULL, next_block bigint NOT NULL CHECK (next_block>=0),
 last_collection timestamptz, head bigint NOT NULL DEFAULT 0, finalized bigint NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS bridge.blocks (
 chain_id bigint NOT NULL REFERENCES bridge.networks(chain_id), block_number bigint NOT NULL,
 block_hash text NOT NULL, parent_hash text NOT NULL, PRIMARY KEY(chain_id,block_number)
);
CREATE TABLE IF NOT EXISTS bridge.observations (
 source_chain bigint NOT NULL, source_bridge text NOT NULL, block_number bigint NOT NULL, block_hash text NOT NULL,
 transaction_hash text NOT NULL, log_index bigint NOT NULL, transfer_id text NOT NULL,
 canonical boolean NOT NULL DEFAULT true, observed_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(source_chain,source_bridge,block_hash,transaction_hash,log_index)
);
CREATE INDEX IF NOT EXISTS observations_transfer ON bridge.observations(transfer_id,canonical);
CREATE TABLE IF NOT EXISTS bridge.transfers (
 id text PRIMARY KEY, source_chain bigint NOT NULL, destination_chain bigint NOT NULL,
 source_block bigint NOT NULL, source_block_hash text NOT NULL, source_tx text NOT NULL, log_index bigint NOT NULL,
 recipient text NOT NULL, source_nonce bigint NOT NULL CHECK(source_nonce>=0), amount numeric(78,0) NOT NULL CHECK(amount>0),
 destination_signer text NOT NULL, state text NOT NULL,
 error_code text, attempts integer NOT NULL DEFAULT 0 CHECK(attempts>=0),
 destination_nonce bigint CHECK(destination_nonce>=0), gas_price numeric(78,0), signed_raw text, destination_hash text,
 destination_block bigint, destination_block_hash text,
 observed_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
 last_attempt timestamptz, next_attempt timestamptz NOT NULL DEFAULT now(),
 CONSTRAINT transfer_state CHECK (state IN ('observed','waiting_finality','source_finalized','destination_prepared',
 'destination_submitted','destination_finalized','waiting_gas','waiting_pause','waiting_rate',
 'retryable_failure','rejected','intervention_required')),
 CONSTRAINT signed_requires_nonce CHECK (signed_raw IS NULL OR (destination_nonce IS NOT NULL AND destination_hash IS NOT NULL AND gas_price IS NOT NULL)),
 CONSTRAINT distinct_chains CHECK(source_chain<>destination_chain),
 UNIQUE(destination_chain,destination_signer,destination_nonce)
);
CREATE TABLE IF NOT EXISTS bridge.nonces (
 chain_id bigint NOT NULL, signer text NOT NULL, next_nonce bigint NOT NULL CHECK(next_nonce>=0), PRIMARY KEY(chain_id,signer)
);
CREATE TABLE IF NOT EXISTS bridge.attempts (
 transfer_id text NOT NULL REFERENCES bridge.transfers(id), attempt integer NOT NULL,
 destination_chain bigint NOT NULL, attempted_at timestamptz NOT NULL, PRIMARY KEY(transfer_id,attempt)
);
CREATE INDEX IF NOT EXISTS attempts_window ON bridge.attempts(destination_chain,attempted_at);
CREATE TABLE IF NOT EXISTS bridge.reconciliations (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, observed_at timestamptz NOT NULL, state text NOT NULL, report jsonb NOT NULL
);
