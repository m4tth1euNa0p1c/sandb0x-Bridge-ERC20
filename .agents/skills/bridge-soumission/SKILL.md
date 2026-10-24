---
name: bridge-soumission
description: "Développer ou vérifier le chemin T3l4N entre transaction préparée, signature persistée et diffusion RPC."
---

# Réconcilier l'envoi d'une transaction

**Entrées.** Transfert finalisé source, nonce réservé, transaction signée et limites de tentative.

## Procédure

1. Persister les octets signés et leur hash avant diffusion pour pouvoir reconnaître un envoi dont la réponse est perdue ; protéger cet artefact selon sa sensibilité.
2. Après timeout, rechercher hash, reçu et état processed destination avant de décider d'une rediffusion des mêmes octets.
3. Enregistrer chaque diffusion et sa réponse sans confondre acceptation RPC, inclusion et finalité ; traiter already known comme un indice à réconcilier.
4. Si une politique de remplacement est autorisée, garder même nonce et même intention métier, borner les frais et relier les hashes.

**Livrable.** Journal de tentatives et expérience d'envoi dont la réponse est volontairement perdue.

**Limite.** Aucun mint compensatoire après simple timeout et aucun nouveau nonce avant résolution de l'ambiguïté.
