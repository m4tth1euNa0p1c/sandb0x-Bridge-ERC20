# Résultats du jalon 1

Le jalon 1 est vérifié dans son périmètre d'infrastructure et d'outillage.
**Le bridge ERC20, les transferts, le relayer et le signataire ne sont pas implémentés.**

Commit source testé : `991df1d6d7c5eb0642e9a51501a9018c792aab4a`. Empreinte exacte des sources :
`ac9da09f58333828bb050b83774e66a5010f382e7d89a4e7e5e389a3688d0956`. Les rapports sont ajoutés dans un commit ultérieur.
Les modifications non commitées au début des campagnes ne concernent que les
campagnes antérieures sous `evidence/` ; les sources testées sont figées.

| Profil | Campagne UTC | Contrôles réussis | Preuve |
|---|---|---|---|
| local-fast | 2026-10-24T20:29:10Z → 2026-10-24T20:30:32Z | 11/11 | <a href="../evidence/20261024T202910Z-local-fast/manifest.json">Manifeste JSON</a> |
| local-besu | 2026-10-24T20:30:35Z → 2026-10-24T20:32:03Z | 11/11 | <a href="../evidence/20261024T203035Z-local-besu/manifest.json">Manifeste JSON</a> |

Résultats observés :

- 47 tests d'outillage réussis sur Windows, puis les mêmes 47 via le wrapper POSIX
  dans un conteneur Python Linux ; aucun test applicatif ERC20 exécuté.
- 50 définitions d'agents et 50 skills validés ; 50 contrôles officiels de skills
  réussis. Quatre exercices comportementaux ciblés ont été réalisés. Cela ne
  démontre pas l'efficacité des 50 rôles sur des missions réelles.
- Anvil 1.3.1 : réseaux 31337/31338 ; Besu 26.10.0 QBFT mono-validateur : 31339,
  avec une seconde chaîne Anvil 31340. Aucun réseau TELA véritable interrogé.
- Sept services par profil portent les restrictions vérifiées. Les contrôles
  réseau autorisés réussissent, la tentative inter-réseaux par IP échoue ;
  les fichiers témoins et secrets des autres compartiments restent inaccessibles
  dans les scénarios testés.
- Témoin SQL et états de nœuds conservés après arrêt et recréation des conteneurs.
  Cela ne valide aucun checkpoint ni nonce de relayer.
- Construction MkDocs stricte et scan Gitleaks réussis. Le contrôle positif du
  scan détecte le credential synthétique. L'intégration est refusée explicitement.

Les 15 affirmations sont décrites dans [le registre](claims.yaml) : 11 vérifiées
localement, une vérifiée sur Besu local, deux bloquées et une proposée. Le tableau
recalcule l'obsolescence si les sources, définitions ou artefacts changent.

## Historique conservé

La campagne `20261024T202049Z-local-fast` avait réussi sur 26d03f9. La campagne
`20261024T202323Z-local-besu` avait réussi ses tests d'infrastructure mais échoué
au scan sur un SHA-256 public pris pour une clé. Elles sont historiques pour le
code actuel. L'exception du scan et le contrôle positif sont documentés dans
[sécurité](securite.md). Les échecs de ports, d'IPAM et de JNI sont consignés dans
[le journal](journal.md).

## Limites restantes

VM et moteur dédiés non établis sur l'hôte partagé actuel. Filtrage des sorties
par destination non démontré. Pas de tests de protocole, fuzzing, invariants,
concurrence du relayer, crash applicatif, réorganisation ou réconciliation d'offre.
Pas de compilation .NET/Solidity au J1, ni de run GitHub Actions distant.
Prometheus et Grafana ne sont pas démarrés.

Sepolia et TELA : non exécutés. Accès, identités, ABI, rôles, clés et gas de test
restent à obtenir selon [les informations manquantes](informations-manquantes.md).
Le démarrage Besu ne constitue pas une validation des contrats futurs.

## Consultation et reproduction

`python scripts/bridge.py up --profile local-fast`, `test`, `prove --profile local-fast`,
`docs`, `status` et `down` sont exécutables ; `bootstrap` prépare un clone neuf.
Consulter [l'installation](installation.md) pour les prérequis.
Le tableau sur `http://127.0.0.1:18080/status/` est un instantané UTC. Relancer
`status` pour le rafraîchir. La disponibilité dépend de l'hôte.
