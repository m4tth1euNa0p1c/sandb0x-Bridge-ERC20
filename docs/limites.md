# Limites, risques et charge

## Ce que la livraison permet d'établir

Les contrats, le signataire, le relayer persistant, les scénarios de panne et la
supervision existent dans le dépôt. Les tests isolés ne suffisent pas à conclure
à la livraison locale complète : celle-ci exige les campagnes de démarrage,
aller-retour, reprise, cloisonnement et documentation correspondant exactement
aux sources. Leur statut courant est dans [les résultats](resultats.md) et le
[registre](claims.yaml), dont TRANSFER-001, RESILIENCE-001 et BESU-PROTO-001.

La VM dédiée n'est pas démontrée sur l'hôte Windows initial partagé. Le moteur
Docker demeure une autorité étendue. La liste de destinations documentée n'est
pas un filtrage effectif de toutes les sorties hôtes. Des tests réussis en
conteneurs ne corrigent pas ces frontières absentes.

## Risques fonctionnels et opérationnels

- Le relayer est autorisé : sa clé ou son accès au signataire peut produire des
  mints frauduleux. L'anti-rejeu, les plafonds et la pause ne prouvent pas le burn.
- Les administrateurs peuvent réattribuer des rôles ; celui du token peut
  autoriser des émissions externes. La réconciliation ne constitue pas un audit
  exhaustif des émissions et destructions qui se compensent.
- La finalité Anvil est une convention de confirmations. Le QBFT mono-validateur
  local ne démontre ni tolérance byzantine ni finalité TELA.
- La reprise n'est pas une transaction atomique distribuée. Certains résultats
  RPC, nonces ou réorganisations exigent une intervention.
- Aucun remplacement automatique de frais n'est implémenté. Un nonce bloqué
  peut arrêter la destination ; aucune compensation automatique n'est produite.
- Les clés résident dans des fichiers de test. Chiffrement de sauvegarde,
  rotation complète, contrôle matériel, restauration de sauvegarde et haute
  disponibilité ne sont pas livrés comme garanties.
- Une paire est définitive pour ce bridge. Migrer contrats ou comptes nécessite
  une procédure de traitement du transit et de migration de l'état persistant.
- La recherche d'ancêtre est bornée à 128 blocs. La réconciliation relit les
  completions depuis le déploiement et parcourt l'historique ; son coût augmente
  avec durée et activité. Les états historiques Anvil consomment aussi du stockage.
- Les métriques peuvent être absentes, anciennes ou arrondies. Les flottants
  Grafana ne servent pas à établir la conservation exacte des unités ERC20.
- Les scans sont limités à leurs règles et à leur date. Épingler une version ne
  garantit pas l'absence de vulnérabilité.

Les tokens TELA existants ne sont pas déclarés compatibles. Sans interfaces
et permissions burn/mint vérifiées, une autre architecture (lock/mint, garde
ou modification explicitement autorisée) exige ADR et nouveaux tests.
Aucune permission d'un token existant n'est modifiée ici.

## Préconditions de l'intégration externe

L'intégration reste désactivée. Les [informations manquantes](informations-manquantes.md)
comprennent confirmation du réseau de test, chain ID et identité, RPC/VPN/
certificats/authentification, version Besu et consensus réels, configuration
EVM, finalité observable, ERC20/ABI/decimals/rôles, droits et fonds de test.

Les faucets fournissent du gas natif ; ils ne garantissent pas le token ERC20.
Les clés publiques d'Anvil ne doivent jamais servir sur un réseau partagé.
Un succès Sepolia ne vaudrait pas validation TELA ; Besu local ne valide aucun
de ces deux réseaux externes.

## Charge projetée, non mesurée

Aucun débit soutenu, percentile de latence, capacité disque à long terme ou
objectif de disponibilité n'a été mesuré. Un intervalle de bloc configuré et
la durée d'un test ne constituent pas un benchmark du bridge.

Méthode de projection : décomposer le travail restant en interfaces inconnues,
recette reproductible, procédures et revue indépendante ; séparer travail et
délais d'accès externes. Les difficultés de persistance, d'historique RPC et de
lecture interchaîne observées rendent une date précise prématurée.

| Lot restant | Ordre de charge projeté et dépendances |
|---|---|
| Recette sur VM dédiée et répétition des pannes | Plusieurs jours après disponibilité de l'hôte ; réévaluer sur les échecs réels |
| Adaptation Sepolia puis TELA de test | Plusieurs jours à plusieurs semaines selon accès, droits ERC20 et finalité ; attente externe séparée |
| Sauvegarde/restauration, rotation, runbooks et revue indépendante | Plusieurs semaines de travail spécialisé selon le périmètre |
| Évolution de la confiance (attestations ou preuves) | Nouveau projet d'architecture, non chiffrable sans mécanisme et exigences définis |

Ces projections ne mesurent pas la productivité de la session et ne sont pas un
engagement. Les compétences couvrent Solidity/OpenZeppelin/Foundry, .NET/Nethereum,
SQL transactionnel, Linux/Compose, EVM/Besu, réseau, sécurité des clés,
exploitation et preuves. Une revue indépendante doit être distincte de l'auteur.

## Référentiels et applicabilité à confirmer

L'entité opératrice, la juridiction et l'activité financière ne sont pas connues.
Aucun test logiciel ne détermine à lui seul une obligation ou certification.

| Catégorie | Traitement dans ce projet |
|---|---|
| Obligation réglementaire applicable | À identifier avec l'entité et le juridique ; [DORA, règlement UE 2022/2554](https://eur-lex.europa.eu/eli/reg/2022/2554/oj) est une référence à examiner selon le champ réel |
| Référentiel volontaire | Le [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework) fournit un cadre de gestion des risques ; aucune adoption ou certification du projet revendiquée |
| Politique interne | Accès, conservation, changements, incidents et responsabilités à fournir et valider par l'organisation |
| Bonne pratique technique | Moindre privilège, limitations explicites, reprise, tests contradictoires et traçabilité des versions |

Sources officielles consultées le 24 octobre 2026 : page NIST accessible ;
EUR-Lex impose un contrôle anti-robot à l'accès automatisé. Aucune analyse
juridique d'article ni applicabilité de DORA n'est revendiquée.
