# Clés, menaces et frontières

**Exigences.** Aucun mainnet, aucun actif réel, uniquement des clés de test.
Aucun secret dans Git, rapports, logs ou captures. Les rôles des contrats et la
signature séparée restent à implémenter ; voir [ADR-0002](adr/0002-protocole.md).

**Implémentation J1.** Utilisateurs numériques non root, rootfs en lecture seule,
capabilities ALL supprimées, no-new-privileges, tmpfs bornés, quotas mémoire/CPU/PID,
journaux tournants 2 × 5 Mo, ports hôtes loopback, réseaux internes distincts.
Aucun service ne reçoit le socket Docker ni le répertoire personnel de l'hôte.
Les passerelles de consultation ont un réseau edge distinct avec masquerading
désactivé ; les nœuds et services de données restent sur réseaux internes.
Les affirmations ISO-001 et ISO-002 indiquent les vérifications et leur périmètre.

PostgreSQL reçoit un mot de passe aléatoire créé localement, via un fichier
Compose secret. Hors Swarm, ce fichier reste un montage de l'hôte, sans chiffrement
de coffre. Sous Unix, le répertoire parent est en 0700 et le fichier monté en
0444 pour que le compte du conteneur puisse le lire ; Compose ne remappe pas
magiquement son propriétaire. Sous Windows, cette recette ne remplace pas une
ACL NTFS et une VM dédiée. La base n'a pas de port publié ; le compte de bootstrap
est administrateur. Un compte applicatif à privilèges réduits est requis au J2.

**Test de cloisonnement.** Un serveur témoin joignable depuis le réseau signing
sert de contrôle positif, y compris via son IP. Une sonde du réseau database
tente la même IP et doit échouer. Une autre vérification monte un fichier public
hors dépôt comme contrôle positif, puis vérifie son absence sans montage. Le
témoin signataire peut lire son propre fichier, mais pas celui de PostgreSQL ;
la base ne reçoit pas le témoin signataire. La sonde vérifie également son UID,
ses capacités effectives, no-new-privileges et le refus d'écriture à la racine.
Ce scénario ne couvre pas toutes les voies réseau de Docker Desktop.

**Limites.** Le processus Codex hôte et ses enfants peuvent lire un témoin hors
dépôt. Le moteur Docker existant est partagé ; aucune ACL ne le limite aux
ressources du bridge. Les réseaux Compose ne confinent pas un administrateur de
l'hôte ou du moteur. La liste `sandbox/egress-policy.json` n'est pas un contrôle
de destinations effectif pour l'installation, et ne garantit pas de filtrage
DNS ou de suppression des accès spéciaux à l'hôte Docker Desktop.
La désactivation du masquerading n'est pas assimilée à un pare-feu de destinations.

**Modèle de menace.** Clé executor compromise : mint indu possible. Admin
compromis : droits et configuration modifiables. RPC malveillant : faux événements
ou fausse finalité ; vérifier identité, hashes et cohérence ne transforme pas un
RPC en preuve de consensus. Base perdue : reprise et réconciliation nécessaires.
Hôte compromis : contournement possible de tous les compartiments de cette VM.
Les plafonds proposés ne sont pas encore appliqués par du code métier.

**Avant intégration.** Identité via chain ID, genesis attendu, code/adresses des
contrats et accord sur le réseau de test ; clés distinctes, droits minimaux,
gas borné, destinations filtrées et politique de finalité validée. Rien de cela
n'est déduit d'un succès local.
