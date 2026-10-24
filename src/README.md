# Services du bridge local

- `Bridge.Relayer` : collecte historique, checkpoints PostgreSQL, finalité locale,
  nonces, reprise, réconciliation, `/status` et `/metrics`.
- `Bridge.Signer` : signature EIP-155 à valeur native zéro, politique restrictive
  et authentification de service ; seules ses instances lisent les clés executor.
- `Bridge.Operator` : outil ponctuel d'administration des simulations locales,
  sans serveur HTTP, utilisé pour le déploiement Besu et jamais pour une chaîne partagée.

Les images sont compilées avec le SDK et le runtime épinglés. Les verrous NuGet
contiennent les dépendances transitives ; `NuGet.config` limite les sources à
NuGet officiel. Les tests de logique et HTTP utilisent des doubles RPC ; les
preuves d'échanges réels et de persistance sont des campagnes séparées.

Le contrat d'interface est décrit dans `docs/adr/0004-interfaces-application.md`.
La collecte par lots de 32 blocs vérifie `nextNonce()` pour détecter une réponse
de logs incomplète. Un verrou PostgreSQL sérialise chaque compte destination.
Les octets signés et leur hash sont conservés avant diffusion. Un timeout ne
déclenche aucun mint compensatoire ni remplacement automatique de transaction.

La convention Anvil attend trois blocs **après** l'inclusion. Le profil QBFT
mono-validateur utilise le bloc accepté localement et ne démontre aucun consensus
de TELA. Les deux identités et permissions sont vérifiées avant chaque cycle.

La réconciliation compare offres et transit dans les deux sens à des coupures
dont les hash sont relus. Une coupure causale incohérente reste inconclusive.
Une émission externe produit un écart à enquêter ; la référence ne s'ajuste pas
automatiquement. La lecture historique des crédits est linéaire en nombre de
blocs : aucune estimation de performance de production n'est déduite de ces tests.
