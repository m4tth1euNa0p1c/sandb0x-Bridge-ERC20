# Informations manquantes et blocages

Dernière revue : 2026-10-24. Aucun de ces éléments n'est déduit d'un Besu local.

| ID | Information / action attendue | Conséquence | Responsable à désigner |
|---|---|---|---|
| ENV-01 | Machine/VM de développement dédiée, compte et moteur Docker réservés au projet | L'hôte actuel partagé ne satisfait pas cette frontière | Exploitation |
| TELA-01 | Confirmation écrite environnement de test, identité réseau, chain ID et hash genesis de référence | Intégration désactivée | Équipe TELA |
| TELA-02 | RPC HTTP, WebSocket éventuel, VPN, ACL, certificats et authentification | Pas d'interrogation ni de déploiement TELA | Équipe TELA |
| TELA-03 | Version Besu, consensus, forks EVM activés, disponibilité des tags de finalité | Aucune politique de finalité TELA autorisée | Équipe TELA |
| TELA-04 | Adresse ERC20, ABI, decimals, rebase/frais éventuels et rôles burn/mint | Compatibilité du token existant inconnue | Propriétaire token |
| TELA-05 | Comptes de test, droits de déploiement, administration, exécution et pause | Aucun contrat existant modifié | Administrateurs |
| TELA-06 | Mécanisme d'obtention du gas et provenance des tokens de test | Aucun transfert réel possible | Équipe TELA |
| SEP-01 | RPC Sepolia autorisé, identité attendue et modalités d'accès | Intégration Sepolia non exécutée | Exploitation |
| SEP-02 | Clés de test distinctes, gas de test, adresses et droits des contrats à déployer | Aucun envoi de transaction Sepolia | Équipe projet |
| SEC-01 | Politique de sorties réseau applicable et mécanisme de filtrage vérifié dans la VM dédiée | Une allowlist documentaire ne vaut pas contrôle réseau | Sécurité / exploitation |
| GOV-01 | Entité opératrice, juridiction, politiques internes et règles de conservation | Applicabilité réglementaire à confirmer | Juridique / sécurité |

Les faucets fournissent du gas de test ; ils ne créent pas automatiquement le token
ERC20 du bridge. Aucune clé ni donnée d'authentification ne doit être ajoutée à ce fichier.
La collecte de ces informations ne bloque pas les expériences locales.
