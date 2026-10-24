---
name: bridge-signature
description: "Concevoir ou tester l'interface remplaçable de signature T3l4N, isolée du relayer et de la base."
---

# Définir le service de signature

**Entrées.** Transactions attendues, comptes dédiés, politiques de signature et contrats de destination.

## Procédure

1. Limiter la requête signable par chain ID, adresse destination, sélecteur, valeurs, gas et contexte de transfert ; un signataire qui signe tout RPC ne réduit pas le pouvoir du relayer.
2. Distinguer allocation du nonce, signature et diffusion. La réponse signée doit pouvoir être persistée avant tout envoi, puis identifiée par son hash.
3. Monter la clé uniquement au signataire et tester le refus des requêtes hors politique sans révéler son contenu ; prévoir une interface pour un fournisseur futur.
4. Documenter stockage local de clé de test, authentification entre compartiments et risques résiduels. Ne pas appeler ce stockage HSM.

**Livrable.** Contrat d'interface, politique de refus et tests positifs/négatifs du signataire.

**Limite.** Si le service n'existe pas encore, produire ses contrats et critères, sans déclarer une signature effectuée.
