# Exigences et progression

Source : demande utilisateur du 24 octobre 2026, complétée par la demande d'au
moins 50 agents et 50 skills. Les exigences ci-dessous restent distinctes des
décisions et des résultats mesurés.

| ID | Exigence reçue | Décision / composant | Vérification prévue | Jalon |
|---|---|---|---|---|
| REQ-01 | Inspecter avant modification, préserver Git, branche dédiée | AGENTS, doctor, journal | Commandes et diagnostic conservés | 1 |
| REQ-02 | Profils local-fast, local-besu, integration-testnet | ADR-0001, profils JSON | Validation + démarrage ; intégration refusée | 1 |
| REQ-03 | Compartiments et ressources bornées | Compose, ADR-0001 | Inspection runtime et témoins réseau/fichiers | 1 puis 3 |
| REQ-04 | Versions vérifiées et épinglées | lock images, lock Python, global.json | Digests et versions exécutées | 1 puis chaque lot |
| REQ-05 | Burn/mint, même decimals, rôles séparés, domaine | ADR-0002 | Tests on-chain, fuzzing et invariants | 2–3 |
| REQ-06 | Reprise historique, checkpoints, nonces et ambiguïtés | ADR-0003 | Crash, concurrence, timeout, reorg | 2–3 |
| REQ-07 | Testnet uniquement, signature remplaçable, limites | Profils fermés, ADR-0002 | Identité réseau, rôles, gas et quotas | 2–5 |
| REQ-08 | Aller-retour et réconciliation d'offre | ADR-0002, matrice de tests | Points cohérents et émissions externes explicites | 2–3 |
| REQ-09 | Toute affirmation liée aux preuves exactes | claims.yaml, manifeste | Empreintes et détection d'obsolescence | 1 puis continu |
| REQ-10 | Supervision exploitation + projet horodatée | Tableau instantané, contrat métriques | Absence de fausse donnée en direct | 1 puis 4 |
| REQ-11 | Documentation française générée et sourcée | MkDocs, ADR | Build strict, liens et cohérence | 1 puis continu |
| REQ-12 | Interface de commandes, CI et absence de secrets | scripts/bridge, workflow | Tests outillage et scan Gitleaks | 1 puis continu |
| REQ-13 | Besu local puis Sepolia/TELA réellement vérifiés | Environnements séparés | Campagnes distinctes, jamais un test ignoré validé | 4–5 |
| REQ-14 | 50 agents et 50 skills, amélioration continue | Catalogue spécialisé | Validation structurelle et retours d'usage | 1 puis continu |

**Hypothèses initiales.** Deux tokens de test dédiés, 18 decimals, offre initiale
connue, pas de rebase ni frais de transfert ; relayer autorisé. Ces hypothèses
ne s'appliquent pas automatiquement à un token TELA existant.

**Acceptation du jalon 1.** Diagnostic réel, structure, ADR, configurations de
trois profils, commandes testées, démarrage local lorsque disponible, résultats
conservés et limites documentées. L'acceptation de la livraison locale complète
exige encore les transferts, la reprise, les pannes et la réconciliation.
