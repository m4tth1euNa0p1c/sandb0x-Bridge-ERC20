# Limites, risques et charge

## Limites de cette livraison

Le jalon 1 ne suffit pas à la livraison locale complète demandée : contrats,
relayer, signataire, transferts, reprise, réorganisation, invariants et offre
restent à implémenter. L'identité du véritable TELA et les prérequis Sepolia sont
absents. La VM dédiée n'est pas démontrée par l'hôte Windows partagé actuel.

Les dépendances applicatives candidates ne sont pas encore restaurées ou testées.
Le pin d'une version fixe la reproductibilité, pas l'absence de vulnérabilité.
Les images de supervision épinglées ne sont pas des services en fonctionnement.

## Charge projetée, non mesurée

Estimation initiale par découpage en composants, pour une personne expérimentée
avec revue ponctuelle : 5–10 jours pour contrats et premier aller-retour ;
10–20 jours pour reprise, concurrence et pannes ; 4–8 jours pour recette Besu
et supervision ; 3–10 jours pour intégration testnet une fois les accès obtenus.
Total projeté : 22–48 jours-personne, hors délais d'accès, audit indépendant et
validation juridique. Ces fourchettes ne sont ni un engagement ni une mesure
de productivité. Les replanifier après le jalon 2 sur les difficultés observées.

Compétences : Solidity/ERC20 et tests Foundry, .NET/Nethereum, SQL transactionnel,
réseaux/containers Linux, exploitation EVM/Besu, sécurité des clés et traçabilité.
Aucun débit ou temps de transfert métier n'a été mesuré. Les blocs de deux
secondes configurés ne sont pas une mesure de performance du bridge.

## Applicabilité réglementaire

L'entité opératrice, la juridiction et le service financier éventuel sont
inconnus. Aucune obligation réglementaire n'est déclarée applicable à ce laboratoire.
Pour une activité entrant dans son champ, le texte DORA est une source à faire
examiner par le juridique : [règlement UE 2022/2554](https://eur-lex.europa.eu/eli/reg/2022/2554/oj).
L'accès automatisé au texte a rencontré un contrôle anti-robot lors de cette
session ; aucune analyse d'article n'est revendiquée.

Le [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework) peut servir
de référentiel volontaire de gestion des risques ; son adoption interne n'est
pas établie. Les politiques internes (conservation, validation des changements,
gestion des accès) restent à obtenir. Le moindre privilège, les tests de reprise
et la preuve de versions sont ici des bonnes pratiques techniques. Aucun test
logiciel n'accorde une certification réglementaire ou une conformité bancaire.
