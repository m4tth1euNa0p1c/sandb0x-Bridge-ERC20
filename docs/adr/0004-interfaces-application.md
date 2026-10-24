# ADR-0004 — interfaces applicatives du démonstrateur local

Date : 2026-10-24. Statut : accepté pour implémentation ; observations dans le registre.

Le relayer et le signataire sont deux exécutables .NET 10 distincts. La clé de
test est lisible uniquement par le signataire. Le relayer conserve le payload
signé en base avant diffusion. Le service de signature ne contacte aucun RPC.
Ce stockage de clé local ne constitue pas un HSM. Le réseau `signing` et un jeton
de service monté seulement dans ces deux compartiments limitent son accès.

Configuration publique commune (JSON camelCase, chemin `BRIDGE_CONFIG`) :

```json
{
  "profile": "local-fast",
  "referenceSupply": "1000000000000000000000000",
  "pollMilliseconds": 1000,
  "rpcTimeoutSeconds": 5,
  "maxAttempts": 12,
  "workers": 2,
  "networks": [{
    "name": "a", "chainId": 31337,
    "genesisHash": "0x...", "clientPrefix": "anvil",
    "rpcUrl": "http://chain-a:8545",
    "tokenAddress": "0x...", "bridgeAddress": "0x...",
    "signerAddress": "0x...", "startBlock": 0,
    "finalityMode": "confirmations", "confirmations": 3,
    "maxTransfer": "1000000000000000000000",
    "gasLimit": 350000, "maxGasPriceWei": "100000000000",
    "keyFile": "/run/secrets/key_a"
  }]
}
```

Les deux réseaux sont obligatoires. Seules les paires locales 31337/31338 et
31339/31340 sont acceptées. Le relayer vérifie genesis, client, code aux adresses,
decimals et paire. Un problème d'identité interdit la soumission.

`POST /sign` (JSON) reçoit `chainId` (entier), `nonce` (chaîne décimale),
`gasPriceWei` (chaîne décimale), `gasLimit` (entier), `to` (adresse), `data`
(hex). Valeur ETH toujours zéro. En-tête `X-Bridge-Token` lu depuis
`BRIDGE_SIGNER_TOKEN_FILE` ; jamais journalisé. Réponse : `rawTransaction`,
`transactionHash`, `signerAddress`. Aucun de ces payloads n'est journalisé.
Le signataire décode `completeTransfer(uint256,address,address,uint256,uint256,address)`
et borne destination, domaine, montant, gas et fréquence. `GET /health` retourne
seulement la disponibilité. Le relayer utilise `BRIDGE_SIGNER_URL`.

Le token de base PostgreSQL est lu depuis `BRIDGE_DB_PASSWORD_FILE` ; hôte, port,
utilisateur et base sont des variables distinctes. Le compte applicatif
`bridge_app` est distinct de l'administrateur `sandbox_admin`.

Contrats : nonce source initial zéro ; identifiant et événements définis dans
ADR-0002 et le code. Paire immuable après configuration initiale pour éviter
de bloquer les burns en transit par un remapping. Les plafonds sont bornés dans
le contrat et la politique du signataire. Un changement exige de nouveaux tests.

La collecte est historique, avec checkpoint transactionnel et réexamen des
observations avant finalité. Chaque réseau source utilise un verrou PostgreSQL
pour la collecte. Les crédits utilisent un verrou par compte destination et
une réservation durable de nonce. Un seul payload signé est conservé par
transfert ; les reprises rediffusent les mêmes octets après réconciliation.
Le remplacement de frais n'est pas automatique dans cette version : un nonce
bloqué finit en intervention requise, sans créer un autre transfert.

Les hooks de panne sont exclusivement réservés aux profils locaux et explicites.
Les tests doivent distinguer panne simulée dans un test isolé et incident exercé
sur les services. Aucune activation Sepolia/TELA n'est ajoutée par cet ADR.
