# Objectif et état réel

Construire un démonstrateur ERC20 burn/mint bidirectionnel avec relayer autorisé,
deux chaînes, PostgreSQL, signature séparée et traçabilité des affirmations.
Le périmètre demandé comporte cinq jalons ; cette livraison traite le **jalon 1**.

**Implémenté au jalon 1 :** outillage de diagnostic, installation séparée,
profils locaux, refus de l'intégration, restrictions Compose, vérifications
d'infrastructure, manifeste de preuves et documentation.

**À implémenter :** contrats, relayer, signataire, transferts, schéma de reprise,
supervision métier, scénarios de panne du bridge et intégration réelle.
La présence de PostgreSQL ou de deux nœuds ne valide pas ces fonctions.

Consulter [les résultats](resultats.md), [le registre JSON/YAML](claims.yaml),
[le journal](journal.md) et [les informations manquantes](informations-manquantes.md).
Le registre utilise les statuts proposé, implémenté, vérifié_local,
vérifié_besu_local, vérifié_sepolia, vérifié_tela, bloqué et obsolète.

Le [tableau local](status/) est généré par `python scripts/bridge.py status`.
Il affiche l'heure UTC du relevé et les services arrêtés ou injoignables. Il ne
s'actualise pas automatiquement. Aucune session Codex n'est promise permanente.
