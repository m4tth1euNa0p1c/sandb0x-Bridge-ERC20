---
name: bridge-logs
description: "Implémenter ou examiner les logs structurés T3l4N d'un transfert et de ses tentatives."
---

# Corréler les journaux structurés

**Entrées.** Transitions du relayer, identifiants de domaine et règles de confidentialité.

## Procédure

1. Émettre transfer_id, chaîne, étape, attempt_id, tx hash public utile et classe d'erreur en champs structurés ; conserver timestamps UTC.
2. Distinguer état observé et action tentée, notamment avant diffusion RPC. Un message submitted ne doit pas annoncer finalisé.
3. Exclure clés, mnemonics, chaînes de connexion, headers d'authentification et URL RPC secrètes ; assainir aussi les erreurs provenant des dépendances.
4. Tester corrélation après redémarrage et rotation des fichiers, puis vérifier que les preuves exportées restent lisibles sans exposer de données sensibles.

**Livrable.** Schéma de logs et trace d'un scénario exécuté de bout en bout lorsque le relayer existe.

**Limite.** Ne pas recopier aveuglément le corps d'une exception réseau ou une configuration complète dans un log.
