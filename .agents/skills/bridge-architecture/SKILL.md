---
name: bridge-architecture
description: "Écrire ou réviser un ADR T3l4N lorsque le modèle de transfert, une frontière de confiance ou un composant change."
---

# Choisir une architecture de bridge

**Entrées.** Exigence concernée, code présent, profils et expériences disponibles.

## Procédure

1. Distinguer le protocole burn/mint, le transport des événements et l'exploitation. Une base PostgreSQL cohérente ne rend pas atomiques deux chaînes.
2. Comparer l'option retenue à une alternative réellement applicable : permissions requises sur le token, surface de mint, reprise, dépendances et limites vérifiables.
3. Décrire chaque frontière avec le détenteur du pouvoir et les messages qu'il peut falsifier. Conserver la distinction entre Besu simulé et véritable TELA.
4. Rédiger l'ADR avant une substitution de stack ; associer critères d'acceptation et expériences discriminantes. Une option future reste proposée tant que son code et ses tests manquent.

**Livrable.** ADR daté avec décision, conséquences, alternatives et liens vers exigences, code et preuves.

**Limite.** Ne pas conclure sur l'architecture TELA si identité, consensus ou permissions ne sont pas documentés.
