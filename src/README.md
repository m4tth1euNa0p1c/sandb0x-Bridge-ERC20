# Composants applicatifs — à implémenter

Le relayer .NET 10 LTS / Nethereum et le service de signature sont prévus au jalon 2.
Il n'existe pas encore de worker, d'API de signature, de schéma de transferts ou
de mécanisme de reprise. PostgreSQL démarré au jalon 1 ne prouve pas leur fonctionnement.
L'interface de signature devra être remplaçable, avec clés de test en fichiers
montés exclusivement dans le signataire. Ce stockage local ne constitue pas un HSM.
Voir `docs/adr/0003-reprise-finalite.md` et `docs/architecture.md`.
