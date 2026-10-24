# Contrats — jalon 2

Aucun contrat ERC20 ou bridge n'est encore implémenté. `foundry.toml` fixe la cible
London, solc 0.8.30, les paramètres de compilation et les budgets de tests futurs.
Le succès de l'infrastructure au jalon 1 ne démontre ni burn/mint ni conservation
de l'offre. OpenZeppelin 5.4.0 est la base candidate ; son code sera verrouillé
avec les dépendances et testé lors de l'implémentation, après revue des avis de sécurité.
Voir `docs/adr/0002-protocole.md`.
