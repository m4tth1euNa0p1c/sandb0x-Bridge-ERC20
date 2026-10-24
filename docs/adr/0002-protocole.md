# ADR-0002 — protocole et confiance, avant implémentation

Date : 2026-10-24. Statut : décision de conception, non implémentée.

**Exigence.** Burn/mint bidirectionnel, anti-rejeu, rôles distincts et confiance explicite.

**Décision.** Deux tokens de test dédiés, non évolutifs pour la première expérience,
18 decimals, sans rebase ni frais. Le bridge source consomme l'autorisation de
l'utilisateur, brûle et émet dans une transaction. Le bridge destination calcule
l'identifiant, vérifie le domaine et le rôle d'exécution, marque processed puis
mint dans la même transaction ; tout revert annule également processed.

Identifiant proposé : `keccak256(abi.encode(PROTOCOL_DOMAIN, version,
sourceChainId, sourceBridge, destinationChainId, destinationBridge,
sourceToken, destinationToken, nonce, amountUnits, recipient))`.
Chaque nonce source est monotone et propre au bridge. La destination vérifie
son `block.chainid`, son adresse et la paire autorisée ; `abi.encode` évite les
ambiguïtés de concaténation. Aucun nombre flottant pour les montants.

Rôles : administrateur attribue/retire les rôles et configure les paires ;
pauser suspend ; executor soumet les crédits. Décider précisément du droit de
reprise dans les contrats : proposé administrateur uniquement. Pour le prototype,
le bridge seul reçoit les permissions burn/mint du token ; toute émission de
bootstrap est bornée et enregistrée. Ne pas modifier un token existant sans
vérifier son ABI, ses rôles et l'autorisation de son propriétaire.

**Confiance.** Le relayer autorisé atteste ce qu'il observe. Le rôle de mint n'est
pas une preuve cryptographique du burn source. Une clé executor compromise peut
autoriser des émissions frauduleuses dans les limites du contrat ; un admin
compromis peut changer les droits ou les plafonds. L'anti-doublon, les plafonds
et la pause réduisent certaines conséquences, pas cette confiance fondamentale.

La pause des crédits peut laisser des burns en transit. Il n'y a ni compensation
automatique après timeout ni atomicité distribuée entre chaînes et PostgreSQL.
Attestations multiples ou preuves vérifiées on-chain sont des options futures.

**Réconciliation proposée.** À deux hauteurs sources/destinations cohérentes :
`supplyA + supplyB + Σ(burns finaux non crédités au point destination) =
referenceSupply + externalMints - externalBurns`.
Éviter un double compte via l'identifiant complet et le sens du transfert ;
enregistrer séparément émissions bootstrap et mouvements externes. Un mint vu
avant son burn dans une fenêtre incohérente doit suspendre la conclusion, pas
faire varier arbitrairement l'offre de référence. Aucun chiffre de réconciliation
n'est disponible au jalon 1.
