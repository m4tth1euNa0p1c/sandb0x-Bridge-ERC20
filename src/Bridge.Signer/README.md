# Signataire de test T3l4N

Ce service .NET 10 signe hors ligne les appels `completeTransfer` autorisés par sa
configuration. Il ne contacte aucun RPC et ne vérifie pas la réalité d'un burn.
Le relayer reste un acteur de confiance : une requête conforme mais mensongère
peut être signée. Le contrat et ses plafonds restent nécessaires.

## Interface et politique

L'interface publique suit [ADR-0004](../../docs/adr/0004-interfaces-application.md).
`GET /health` retourne uniquement `{"status":"available"}` lorsque le service a
démarré avec une configuration et des clés valides.

`POST /sign`, avec `Content-Type: application/json`, accepte exactement :

| Champ | Format / contrôle |
|---|---|
| `chainId` | entier JSON, réseau appartenant à la paire du profil |
| `nonce` | chaîne décimale canonique, 0 à 1 000 000 |
| `gasPriceWei` | chaîne décimale canonique, 0 à la borne configurée, au plus 100 gwei |
| `gasLimit` | entier JSON, au moins le gas intrinsèque du calldata, au plus la borne configurée ≤ 500 000 |
| `to` | adresse du bridge destination configuré |
| `data` | hex `0x`, exactement 196 octets : sélecteur et six mots ABI statiques |

Le sélecteur doit être celui de
`completeTransfer(uint256,address,address,uint256,uint256,address)`.
Les six champs décodés sont le chain ID source, son bridge, son token, le nonce
source, le montant entier et le destinataire. Le domaine doit correspondre à
l'autre réseau configuré ; le nonce source est borné à 1 000 000, le montant est
strictement positif et inférieur ou égal aux plafonds des deux réseaux. Les
adresses nulles et les paddings ABI non canoniques sont refusés.

La valeur ETH est imposée à zéro dans la construction de la transaction. Un champ
`value`, même nul, est rejeté comme champ inconnu. Les propriétés JSON dupliquées,
les champs manquants, les types incorrects et les corps dépassant 4 096 octets sont
refusés. Seuls `local-fast` (31337/31338) et `local-besu` (31339/31340) sont admis.

Le jeton `X-Bridge-Token` doit correspondre au fichier `BRIDGE_SIGNER_TOKEN_FILE`.
La comparaison utilise SHA-256 puis `CryptographicOperations.FixedTimeEquals`
sur deux empreintes de 32 octets. Le jeton doit contenir 32 à 256 caractères ASCII
visibles. Le service n'en journalise ni la valeur ni le chemin.

La fréquence est limitée à **10 signatures par minute et par chaîne**, sous
verrou concurrent et avec une horloge monotone. Cette limite est **en mémoire** :
elle est réinitialisée au redémarrage. Chaque nouvelle signature demandée consomme
la fenêtre, même lorsque la requête est identique. Cette limite de service ne
remplace pas un plafond persistant on-chain. Le signataire ne réserve pas les
nonces et ne détecte pas leur réutilisation après redémarrage ; cela relève du
relayer et de son registre persistant.

Les transactions produites sont des transactions legacy avec protection EIP-155.
La réponse contient `rawTransaction`, `transactionHash` et `signerAddress`.
Le relayer doit persister la réponse avant diffusion. Aucune transaction brute,
clé, requête ou en-tête d'authentification n'est journalisé par ce composant.

| Code HTTP | Corps d'erreur |
|---|---|
| 400 | `{"error":"invalid_request"}` |
| 401 | `{"error":"unauthorized"}` |
| 403 | `{"error":"policy_rejected"}` |
| 429 | `{"error":"rate_limited"}`, avec `Retry-After: 60` |
| 500 | `{"error":"signing_failed"}` |

Les réponses n'exposent pas les détails des exceptions. Les erreurs de backend,
y compris de type JSON, restent des erreurs 500 et ne deviennent pas des rejets
de schéma 400. Une requête interrompue par le client peut terminer avec le statut
499. La réponse de signature porte `Cache-Control: no-store`.

## Configuration et clé

`BRIDGE_CONFIG` désigne le JSON public commun. Le lecteur tolère ses métadonnées
supplémentaires, mais refuse les propriétés dupliquées. Chaque réseau doit fournir
`chainId`, `bridgeAddress`, `tokenAddress`, `signerAddress`, `keyFile`,
`maxTransfer`, `gasLimit` et `maxGasPriceWei`. Les deux chemins de clés doivent être
absolus et distincts. L'adresse dérivée de chaque clé doit correspondre à
`signerAddress` ou le service refuse de démarrer.

`ITransactionSignerBackend` constitue le point de remplacement du fournisseur.
`FileKeySigner` est une implémentation pour **clés locales de test** ; ce n'est pas
un HSM. Le processus possède la clé en mémoire. L'effacement de son tableau privé
à l'arrêt ne garantit pas l'effacement de toutes les copies internes aux
bibliothèques ou au runtime.

La commande `--generate-key` crée une clé aléatoire avec le générateur
cryptographique du système et ne remplace jamais un fichier existant. Sa sortie
standard contient seulement l'adresse publique. Les clés de développement Anvil
ne sont pas utilisées. Sous Unix, un nouveau dossier parent est créé en 0700 et
le fichier final en 0444 pour lecture par le compartiment de signature via un
secret Compose. **Un parent déjà existant n'est pas modifié** : l'orchestrateur
doit assurer sa protection sur l'hôte avant de rendre la clé lisible en 0444.
Sur Windows et les bind mounts Docker Desktop, les modes Unix ne prouvent pas
les ACL hôtes ; cette limite doit être traitée dans la VM dédiée.

## Construction et essais exécutés

Le SDK est épinglé par le `global.json` du dépôt à **10.0.402**. Les dépendances
directes sont `Nethereum.Signer 6.1.0` et `Newtonsoft.Json 13.0.4`, avec leurs
transitives verrouillées dans `packages.lock.json`. Le premier restore a tiré
`Newtonsoft.Json 11.0.2` et échoué sur NU1903 ; la référence directe 13.0.4 corrige
cette résolution sans masquer l'avertissement.

Depuis la racine, sous PowerShell avec le SDK local installé :

```powershell
.local/dotnet/dotnet.exe restore tests/Bridge.Signer.Tests/Bridge.Signer.Tests.csproj --locked-mode
.local/dotnet/dotnet.exe test tests/Bridge.Signer.Tests/Bridge.Signer.Tests.csproj --no-restore --configuration Release --logger "trx;LogFileName=signer-tests.trx" --results-directory .local/test-results/signer
.local/dotnet/dotnet.exe publish src/Bridge.Signer/Bridge.Signer.csproj --no-restore --configuration Release --output .local/publish/signer
.local/dotnet/dotnet.exe .local/publish/signer/Bridge.Signer.dll --generate-key .local/cle-test-dediee/key
```

Pour démarrer, renseigner `BRIDGE_CONFIG` et `BRIDGE_SIGNER_TOKEN_FILE`, puis
exécuter la DLL sans argument. L'écoute par défaut est `http://127.0.0.1:8080` ;
`ASPNETCORE_URLS` peut fixer l'écoute interne du conteneur. Aucun changement de
réseau ou démarrage du relayer n'est effectué par cet exécutable.

Au 2026-10-24 : **64 tests réussis, 0 ignoré** avec SDK 10.0.402. Ils couvrent les
quatre chain IDs locaux, récupération de l'expéditeur, décodage des valeurs
signées, refus de domaine/nonce/montant/gas, schéma HTTP, authentification,
limitation concurrente et assainissement des erreurs. Les tests HTTP utilisent
le serveur ASP.NET Core de test en mémoire ; ils ne constituent pas un test de
réseau Docker. Le publish et deux invocations CLI ont aussi été exécutés :
création de clé, puis refus de remplacement (codes 0 puis 2). Aucun contenu de
clé n'a été ajouté aux rapports. L'audit NuGet transitif n'a remonté aucune
vulnérabilité connue après correction, selon les données consultées à cette date.

Rapports locaux : `.local/test-results/signer/signer-tests.trx` et
`.local/signer-cli-probe/results.json`. Ils seront rattachés à une campagne du
dépôt avec son commit et ses empreintes ; cette section ne remplace pas ce
manifeste. Aucune intégration Sepolia ou TELA n'est effectuée par ces tests.

## Sources primaires consultées

- [Nethereum 6.1.0 : LegacyTransactionSigner](https://github.com/Nethereum/Nethereum/blob/6.1.0/src/Nethereum.Signer/LegacyTransactionSigner.cs)
- [Nethereum 6.1.0 : récupération et vérification des signatures](https://github.com/Nethereum/Nethereum/blob/6.1.0/src/Nethereum.Signer/TransactionVerificationAndRecovery.cs)
- [Microsoft : comparaison à durée indépendante des valeurs](https://learn.microsoft.com/en-us/dotnet/api/system.security.cryptography.cryptographicoperations.fixedtimeequals?view=net-10.0)
- [Microsoft : tests d'intégration ASP.NET Core](https://learn.microsoft.com/en-us/aspnet/core/test/integration-tests?view=aspnetcore-10.0)
- [NuGet : Nethereum.Signer 6.1.0](https://www.nuget.org/packages/Nethereum.Signer/6.1.0)
- [NuGet : Newtonsoft.Json 13.0.4](https://www.nuget.org/packages/Newtonsoft.Json/13.0.4)
