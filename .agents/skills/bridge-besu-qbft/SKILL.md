---
name: bridge-besu-qbft
description: "Configurer ou tester le profil Besu local T3l4N avec genesis et consensus reproductibles."
---

# Retour d'expérience local

Si Besu échoue au chargement de RocksDB JNI avec `failed to map segment`,
vérifier le montage du répertoire temporaire Java. Le profil testé utilise
un tmpfs exécutable dédié `/jni-tmp`, borné et réservé à uid1000, en conservant
`/tmp` noexec et la racine en lecture seule. Ne pas généraliser ce diagnostic
à tout échec Java ; conserver la trace observée et retester le démarrage.

# Préparer une simulation Besu QBFT

**Entrées.** sandbox/besu/qbft.json, version Besu verrouillée, profil local-besu et répertoire local de clés ignoré par Git.

## Procédure

1. Documenter nombre de validateurs, blockperiodseconds, epochlength et requesttimeoutseconds. Une configuration mono-validateur ne fournit pas de tolérance byzantine.
2. Générer les clés de nœuds hors Git et conserver uniquement les empreintes du genesis public et la procédure de génération. Ne pas imprimer les clés.
3. Vérifier chain ID, clientVersion, production de blocs et liste de validateurs si l'API QBFT est disponible ; noter les méthodes réellement interrogées.
4. Déployer ultérieurement un contrat de test avec la cible EVM épinglée pour établir la compatibilité de bytecode. Le démarrage seul ne la démontre pas.

**Livrable.** Preuve de la configuration et des expériences sur la version Besu exacte.

**Limite.** Ne déduire ni consensus ni version ni identité du véritable TELA à partir de cette simulation.
