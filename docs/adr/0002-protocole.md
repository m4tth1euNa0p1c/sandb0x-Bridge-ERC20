# ADR-0002 — protocole et confiance

Date initiale et mise à jour : 2026-10-24. Statut : protocole v1 implémenté pour
tokens de test dédiés ; preuves et portée dans [le registre](../claims.yaml).

## Exigence et décision initiale

Réaliser un burn/mint bidirectionnel avec anti-rejeu, rôles distincts et confiance
explicite. Retenir deux tokens non évolutifs à mêmes decimals, sans rebase ni
frais : burn et événement dans la transaction source ; enregistrement de l'ID
et mint dans la transaction destination. Employer des montants entiers et un
identifiant séparé par domaine.

Le modèle suppose des droits burn/mint effectivement disponibles. Il n'a pas été
retenu pour un token TELA existant dont l'ABI et les permissions sont inconnues.
Un modèle lock/mint, une garde ou une modification de token autorisée resterait
une autre décision d'architecture, avec ses risques et tests propres.

## Mise en œuvre observée

`contracts/src/BridgeToken.sol` utilise OpenZeppelin 5.4.0 et 18 decimals. Le
bridge exige le bytecode de cette implémentation dédiée ; les tokens arbitraires,
proxies, frais et rebase sont hors périmètre. La configuration distante exige
18 decimals ; ses adresses et son code sont vérifiés par le relayer, pas par
une lecture interchaîne du contrat.

`requestTransfer` dépense l'allowance utilisateur via `burnFrom`, brûle puis émet
`TransferInitiated`. Un revert annule l'ensemble. Le nonce source commence à
zéro et augmente à chaque burn réussi. Le hash v1 est exactement :

```text
keccak256(abi.encode(
  keccak256("T3L4N_BRIDGE_BURN_MINT"), uint256(1),
  sourceChainId, sourceBridge, destinationChainId, destinationBridge,
  sourceToken, destinationToken, nonce, amount, recipient
))
```

La destination utilise son adresse, son token et son chain ID effectifs.
`completeTransfer` vérifie domaine et exécuteur, marque `processed`, consomme
le quota puis mint dans la même transaction ; un échec de mint annule aussi
processed et quota. Les chemins métier sont protégés contre la réentrance.
Les événements et le vecteur indépendant sont décrits dans
[l'architecture](../architecture.md) et `contracts/vectors/transfer-id-v1.json`.

| Rôle | Pouvoir effectivement implémenté |
|---|---|
| Administrateur du bridge | Attribuer/retirer les rôles, configurer une paire une seule fois, lever la pause |
| `PAUSER_ROLE` | Appeler `pause()` ; ne peut pas lever la pause par ce seul rôle |
| `EXECUTOR_ROLE` | Appeler `completeTransfer` sur la paire configurée |
| `BRIDGE_ROLE` du token | Appeler `mint` et `burnFrom` ; ce dernier dépense l'allowance du détenteur |
| Administrateur du token | Attribuer/retirer `BRIDGE_ROLE`, donc permettre des émissions externes |

`configurePair` est définitif pour une chaîne distante afin de ne pas invalider
un burn en transit par remapping. Le montant maximal, le plafond de mint par
époque et la durée d'époque sont immuables après construction. L'administrateur
ne dispose pas de setter pour ces plafonds ; ses pouvoirs sur les rôles restent
étendus. Les comptes de déploiement locaux séparent administration, pause et
exécution. Seul le bridge reçoit initialement le rôle de token, après l'émission
de bootstrap enregistrée.

## Confiance et limites

Le relayer autorisé atteste ce qu'il observe. Une clé d'exécution compromise
peut fabriquer des mints dans les limites du bridge, sans burn réel. Un accès
compromis au signataire permet aussi des requêtes frauduleuses compatibles
avec sa politique : celui-ci ne contacte aucun RPC et ne détient aucune preuve
du burn. L'administrateur du token peut attribuer un rôle autorisant une
émission externe qui contourne les plafonds du bridge.

L'anti-doublon, les plafonds et la pause réduisent certaines conséquences sans
supprimer cette confiance. Le test de mint forgé par un exécuteur autorisé rend
ce pouvoir explicite. Les attestations multiples ou preuves vérifiées on-chain
sont des évolutions possibles, non des fonctions livrées.

La pause bloque les deux chemins métier et peut laisser des burns en transit.
La levée de pause relève de l'administrateur. Il n'existe ni pause automatique
du contrat par le relayer, ni mint compensatoire après timeout, ni transaction
atomique distribuée entre chaînes et PostgreSQL.

## Réconciliation : proposition et réalisation

La décision initiale proposait un bilan général à coupes cohérentes :

```text
supplyA + supplyB + transit = referenceSupply + externalMints - externalBurns
```

`src/Bridge.Relayer/Reconciler.cs` implémente actuellement le cas **sans émissions
ni destructions externes**, avec une offre de référence fixe issue du bootstrap :

```text
supplyA(coupeA) + supplyB(coupeB) + transit_non_minté(coupes) = referenceSupply
```

Les transferts des deux sens sont dédupliqués par ID. Les collecteurs doivent
couvrir les coupes choisies selon la politique de finalité ; offres, completions
et `processed` sont lus aux hauteurs correspondantes, puis les hashes sont
revérifiés. Un mint présent sans burn dans la coupe source, une couverture
insuffisante, une completion incohérente ou une réorg pendant le contrôle donnent
`inconclusive`, pas une validation ni un ajustement de l'offre de référence.

`balanced` signifie que l'égalité est satisfaite sous ces hypothèses.
`mismatch` demande une enquête ; des émissions et destructions externes qui
se compensent peuvent échapper à ce bilan. Aucun registre exhaustif de flux
externes ni correction autonome d'offre n'est implémenté. Le coût de relecture
augmente avec l'historique ; aucun débit n'est déduit de ces contrôles.

## Vérification et sources

Les tests de contrats vérifient montants, destinataires, permissions, pause,
rejeu, atomicité, fuzzing et invariants sous hypothèses explicites. Les
expériences entre nœuds et la réconciliation ont des preuves distinctes :
CONTRACT-001, TRANSFER-001, RECON-001 et BESU-PROTO-001. Consulter
[les résultats](../resultats.md) pour la version réellement vérifiée.

Références : [OpenZeppelin 5.x](https://docs.openzeppelin.com/contracts/5.x),
[ADR-0003](0003-reprise-finalite.md), [interfaces applicatives](0004-interfaces-application.md)
et [sources officielles](../sources.md). La bibliothèque et les tests locaux
n'attestent aucune compatibilité d'un token TELA non examiné.
