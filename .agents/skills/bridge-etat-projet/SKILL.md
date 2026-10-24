---
name: bridge-etat-projet
description: "Construire ou vérifier la vue T3l4N du commit exécuté, des campagnes et des affirmations."
---

# Exposer un état projet vérifiable

**Entrées.** Registre des claims, manifestes, empreinte courante et observation des services.

## Procédure

1. Afficher commit source et empreinte de travail, profil, dernière campagne, date du relevé et liens vers résultats ; ne pas confondre commit du rapport et commit testé.
2. Recalculer les statuts effectifs lorsque les sources ou définitions d'affirmations changent ; montrer obsolète au lieu de conserver un ancien vert.
3. Séparer exploitabilité actuelle des services et validation historique du code : un test passé ne prouve pas que l'hôte tourne encore.
4. Indiquer les composants non implémentés et les intégrations non exécutées. Tester également l'affichage lorsque Docker ou les RPC sont arrêtés.

**Livrable.** Vue horodatée, liens vérifiables et comportement explicite sur données anciennes.

**Limite.** Aucun rafraîchissement ou disponibilité permanente promis si la page est statique ou si l'hôte peut s'arrêter.
