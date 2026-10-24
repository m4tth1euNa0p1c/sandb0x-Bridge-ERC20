---
name: bridge-exigences
description: "Construire la traçabilité T3l4N lorsqu'une demande, un critère de livraison ou un périmètre de jalon évolue."
---

# Tracer les exigences et les jalons

**Entrées.** Demande utilisateur, exigences existantes, inventaire du dépôt et registre des affirmations.

## Procédure

1. Décomposer la demande en comportements observables ; séparer besoin métier, contrainte d'environnement et document attendu.
2. Associer à chaque exigence un responsable, un jalon, un test attendu et une affirmation stable. Conserver aussi les exigences bloquées ou non encore implémentées.
3. Rechercher les contradictions entre statut du jalon et preuves : démarrage de nœuds, transfert de token et reprise du relayer sont trois réalisations distinctes.
4. Lors d'une demande nouvelle, préserver les critères antérieurs encore applicables ; expliquer les dépendances au lieu de remplacer silencieusement le périmètre.

**Livrable.** Matrice exigence → décision → code → vérification → résultat, avec manques identifiés.

**Limite.** Ne pas déclarer une exigence satisfaite sur la seule présence d'un fichier ou d'un test ignoré.
