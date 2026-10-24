# Diagrammes consultables hors connexion

Les blocs Mermaid des pages Markdown sont rendus en SVG par le navigateur à
partir d'un fichier local. Aucun CDN n'est nécessaire à leur consultation. La
source textuelle reste accessible sous chaque diagramme, et reste visible si
JavaScript est désactivé. Un échec de rendu produit un message explicite.

La distribution officielle **Mermaid 11.16.1** est conservée sans modification
dans `vendor/mermaid-11.16.1/mermaid.min.js` : 3 566 058 octets. Ce coût unique
d'environ 3,4 MiB évite une installation Node ou un chargement distant pour le
site généré. Cette version corrective de la branche 11 a été choisie à partir
des [avis de sécurité officiels](https://github.com/mermaid-js/mermaid/security/advisories/GHSA-3rrr-jr9j-h3q3),
sans passer à la version majeure 12. Ce choix ne constitue pas un audit exhaustif.

Le [manifeste d'origine](vendor/mermaid-11.16.1/upstream.json) conserve URL,
version, intégrité SHA-512 de l'archive npm et SHA-256 des fichiers extraits.
L'archive a été téléchargée depuis le registre npm officiel puis son intégrité
a été vérifiée avant extraction. La [licence MIT](vendor/mermaid-11.16.1/LICENSE.txt)
et les notices incorporées au bundle sont conservées. Le bundle ne contient
aucun import dynamique ; les trois diagrammes actuels sont vérifiés dans le
navigateur avec les requêtes HTTP externes bloquées.

`mermaid-init.js` adapte les blocs `fenced_code` de MkDocs à l'API Mermaid,
utilise le mode de sécurité `strict` et des polices locales. Les diagrammes
larges conservent leur taille avec un défilement horizontal pour rester lisibles.
La coloration highlight.js distante du thème MkDocs est désactivée ; les blocs
de code restent lisibles en texte brut.

Pour vérifier depuis le dépôt préparé :

```sh
python tests/docs_mermaid.py
```

Ce programme construit MkDocs en mode strict dans un répertoire temporaire au
projet, vérifie les empreintes et l'absence de ressources HTML distantes, puis
ouvre les pages avec Chrome ou Chromium déjà installé, en headless et avec un
profil neuf. Il conserve commandes, DOM, captures et résultats sous
`.local/mermaid-validation/`. Il ne modifie aucun service Docker. La présence des
SVG est testée dans le DOM ; la lisibilité des captures doit aussi être inspectée.
Un navigateur absent est un blocage explicite, jamais une validation ignorée.

Sources primaires : [distribution 11.16.1](https://github.com/mermaid-js/mermaid/releases/tag/mermaid%4011.16.1),
[API Mermaid](https://mermaid.js.org/config/usage.html),
[configuration de MkDocs](https://www.mkdocs.org/user-guide/configuration/#theme).
Les résultats de campagne font foi pour les versions effectivement testées.
