# Contrats du démonstrateur

`BridgeToken` est un token de test dédié à 18 decimals, sans frais, rebase ou
proxy. `Bridge` réalise un burn source et un mint destination à la demande d'un
exécuteur autorisé. Le premier nonce source est **0** ; il augmente seulement
quand la transaction de burn réussit.

## Interfaces stables

```solidity
BridgeToken(string name, string symbol, address admin,
            address initialRecipient, uint256 initialSupply)
Bridge(address token, address admin, address pauser, address executor,
       uint256 maxTransfer, uint256 epochMintCap, uint256 epochSeconds)
configurePair(uint256 remoteChainId, address remoteBridge,
              address remoteToken, uint8 remoteDecimals)
requestTransfer(uint256 destinationChainId, address recipient, uint256 amount)
    returns (bytes32 transferId)
completeTransfer(uint256 sourceChainId, address sourceBridge,
                 address sourceToken, uint256 nonce, uint256 amount,
                 address recipient)
```

L'utilisateur approuve **l'adresse du bridge source** sur le token avant
`requestTransfer`. Le token consomme cette allowance dans `burnFrom`. Le bridge
doit posséder `BRIDGE_ROLE` sur son token, attribué après déploiement par
l'administrateur du token. Sans ce droit, le burn ou le mint échoue.

```solidity
TransferInitiated(bytes32 indexed transferId,
    uint256 indexed destinationChainId, address indexed sender,
    address recipient, address sourceToken, address destinationToken,
    address destinationBridge, uint256 nonce, uint256 amount)
TransferCompleted(bytes32 indexed transferId,
    address indexed recipient, uint256 amount)
```

ABI et bytecodes compilés : `out/Bridge.sol/Bridge.json` et
`out/BridgeToken.sol/BridgeToken.json`, générés et ignorés par Git. Les getters
`token()`, `localChainId()`, `pairs(uint256)` retournant `(remoteBridge, remoteToken)`,
`nextNonce()`, `processed(bytes32)`, `paused()`, `maxTransfer()`, `epochMintCap()`,
`epochSeconds()` et `mintedInEpoch(uint256)` permettent les contrôles du relayer.

## Domaine et configuration

L'identifiant utilise exactement :

```solidity
keccak256(abi.encode(
    keccak256("T3L4N_BRIDGE_BURN_MINT"), uint256(1),
    sourceChainId, sourceBridge, destinationChainId, destinationBridge,
    sourceToken, destinationToken, nonce, amount, recipient
))
```

Le helper `computeTransferId` expose ce calcul. Le vecteur
`vectors/transfer-id-v1.json` a été obtenu séparément avec `cast abi-encode`
puis `cast keccak` 1.3.1 ; un test compare le résultat Solidity à cette valeur.
Ce vecteur peut vérifier l'encodage .NET.

La paire est configurée **une seule fois par chain ID distant**. Une réécriture
silencieuse pourrait rendre les burns en transit impossibles à créditer.
Une migration nécessite un nouveau déploiement et une procédure explicite,
non implémentée ici. Le chain ID local est capturé au déploiement : les
opérations métier échouent si le chain ID d'exécution change.

Le constructeur accepte uniquement le **code d'exécution exact** de
`BridgeToken` compilé avec ce projet. Les tokens locaux arbitraires et leurs
extensions sont rejetés ; les decimals configurés doivent être 18. La chaîne
locale ne peut pas vérifier le code distant : opérateur et relayer doivent
vérifier son identité. `remoteDecimals` est une déclaration d'administrateur,
pas une mesure RPC.

## Pouvoirs et confiance

| Contrat / rôle | Pouvoir | Attribution / retrait |
|---|---|---|
| Token / `DEFAULT_ADMIN_ROLE` | Gérer les rôles du token | Administrateur de ce rôle |
| Token / `BRIDGE_ROLE` | `mint` ; `burnFrom` avec allowance | Administrateur du token |
| Bridge / `DEFAULT_ADMIN_ROLE` | Configurer une nouvelle paire, reprendre, gérer les rôles | Administrateur de ce rôle |
| Bridge / `PAUSER_ROLE` | Mettre en pause | Administrateur du bridge |
| Bridge / `EXECUTOR_ROLE` | Appeler `completeTransfer` | Administrateur du bridge |

Le compte admin ne reçoit pas automatiquement les rôles pause ou exécution.
Un même compte peut néanmoins recevoir plusieurs rôles : la séparation logique
ne démontre pas une séparation des personnes. Les changements de rôles émettent
les événements OpenZeppelin. Il n'y a ni timelock, multisignature ni récupération
d'un admin perdu. Renoncer au dernier rôle administrateur peut rendre
l'administration définitivement inaccessible.

Burn et événement sont atomiques sur la source. À destination, `processed`,
quota et mint sont atomiques : un revert du token annule les trois. Un même
identifiant ne peut pas être traité deux fois. Les deux chemins utilisent
`nonReentrant` et sont bloqués pendant la pause ; la reprise est réservée à
l'admin. Un burn peut rester en transit pendant une pause destination.

**Aucune preuve du burn distant n'est vérifiée.** Un exécuteur compromis peut
fabriquer un mint avec un nouveau nonce, montant ou destinataire, dans les
limites applicables. Un test démontre expressément cette possibilité. L'admin
du token peut accorder `BRIDGE_ROLE` à un autre compte et permettre des émissions
externes contournant les limites du bridge. Aucun mint compensatoire automatique
n'est prévu après timeout.

Les trois limites du constructeur sont immuables. Le quota de mint est global
au bridge pour l'époque entière `timestamp / epochSeconds`, toutes paires et
tous exécuteurs confondus. Cette fenêtre est fixe : deux mints autour d'une
frontière peuvent utiliser deux quotas successifs. Fréquence et gas du relayer
relèvent de l'off-chain.

## Compilation et vérification

Prérequis : Python 3.11+, Docker Linux et image Foundry du verrou
`sandbox/versions.lock.json` déjà téléchargée. Depuis la racine :

```text
python contracts/tools/prepare.py
python contracts/tools/verify.py
```

`prepare.py` est la phase d'installation : vérification des sources vendored,
téléchargement solc si absent, puis contrôle SHA-256. Le point primaire
`binaries.soliditylang.org` répondait HTTP 403 lors de la préparation ; le
verrou utilise le dépôt officiel `ethereum/solc-bin` à une révision précise.
`prepare.py --offline` vérifie uniquement ce qui est présent.

`verify.py` compile et teste dans Foundry épinglé, réseau `none`, utilisateur
1000, capacités supprimées, racine en lecture seule et ressources limitées.
Seul `contracts/` est monté, sans socket, home ou secrets ; les sorties locales
sont `out/`, `cache/` et `.toolchain/`. Compilateur : **solc 0.8.30**, cible
**London**, optimiseur **200 runs**. OpenZeppelin **5.4.0** est vendored avec
licence, révision Git, empreinte d'archive et empreinte de chaque fichier dans
`vendor/openzeppelin/SOURCES.json`. Ce verrou n'est pas un audit du bridge.

Le rapport est `.local/contracts-verification.json` à la racine ; `--output CHEMIN`
permet une destination de campagne. Il contient commandes, codes de sortie,
versions, image observée, empreintes des sources, état Git et résultats. La
graine est `0x20261024`. Un changement de source exige une nouvelle campagne.

## Tests et portée

La suite exécutée le 24 octobre 2026 compte **27 tests réussis, aucun échec et
aucun test ignoré** : allers-retours, unités/destinataires, événements,
allowance, rôles/révocations, pause/reprise, doublon, contexte de rejeu,
identité modifiée, rollback du mint et des quotas, limites et token non supporté.
Deux tests de fuzzing exécutent chacun 1 000 cas.

Deux invariants exécutent chacun 256 séquences de 64 appels de handler. Le
modèle utilise deux acteurs et deux directions, une file indépendante d'intents,
des compteurs de burns/mints et des tentatives de doublon, pause et révocation.
Un préfixe fixe de deux burns et d'un mint garantit un état non vide ; un test
distinct exerce chaque action. Les reverts attendus sont vérifiés par appels
bas niveau ; un revert inattendu du handler fait échouer la campagne.

Sous les hypothèses « émissions bootstrap seules, exécuteur honnête, aucune
destruction externe, checkpoints cohérents », les invariants vérifient
`supplyA + supplyB + burns_en_transit = offre_bootstrap` et l'unicité des effets
par identifiant. Ils ne réparent pas un écart en changeant la référence. Émissions
externes et fraude d'exécuteur sortent de ce modèle et doivent produire un écart
dans la réconciliation d'exploitation.

Le harness partage une EVM et utilise `vm.chainId`. Il n'établit pas à lui seul
un transfert entre deux RPC indépendants, la reprise PostgreSQL, les nonces du
relayer, une reorg réelle ou l'exécution Besu. Ces expériences relèvent des
campagnes d'intégration. Aucun résultat Sepolia ou TELA n'est établi ici.
