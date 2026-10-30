# Livrable 1 — document d'architecture Sepolia ⇄ TELA

Réponse au mail d'Alain « Bridge TELA – SEPOLIA » : architecture interne du bridge
burn & mint de l'ERC20 « Stablecoin Euro Talan » entre Sepolia et TELA, démonstration,
analyse des risques, estimation des charges et compétences requises.

**Document à diffuser :** `Livrable-1_Architecture_Bridge_Sepolia-TELA_v1.0.pdf`, à la racine du dépôt
(54 pages A4, signets, sommaire paginé, interne Talan — diffusion restreinte).
Il s'agit d'une **proposition** soumise à validation ; elle ne déclare ni Sepolia,
ni TELA, ni une quelconque préparation à la production comme validés.

## Contenu

| Chemin | Rôle |
|---|---|
| `src/parts/*.html` | Sections du document, dans l'ordre des préfixes ; schémas SVG dessinés et sources Mermaid |
| `src/style.css`, `src/template.html` | Mise en page A4 (CSS Paged Media) |
| `fonts/` | Inter 4 en WOFF2 TrueType (`@fontsource/inter` 5.2.8, licence OFL dans `OFL-Inter.txt`) |
| `build.mjs` | Rendu Chromium/Playwright, Mermaid local `docs/assets/vendor/mermaid-11.16.1`, aucun accès réseau |
| `build_pdf.py` | Deux passes (pagination du sommaire), signets, métadonnées |
| `demo/demo_burn_mint.py` | Démonstration ponctuelle burn/mint sur deux Anvil locaux, relayer joué pas à pas |

## Régénérer le PDF

Prérequis : Node.js 22 avec Playwright et Chromium, Python 3.12+ avec `pypdf`. Le PDF est écrit à la racine du dépôt.

```sh
python3 livrables/livrable-1/build_pdf.py
```

Le script échoue si un diagramme ne se rend pas, si une image manque ou si la
pagination change entre les deux passes. Les octets du PDF varient d'un rendu à
l'autre (dates de création) ; le contenu ne dépend que des sources de ce dossier.

## Rejouer la démonstration

Prérequis : `forge` 1.3.1, `anvil` et `cast` 1.8.4 (archives officielles Foundry) et
le binaire solc 0.8.30 dont le SHA-256 figure dans `contracts/solc.lock.json`.

```sh
python3 livrables/livrable-1/demo/demo_burn_mint.py --tools <bin Foundry> --solc <solc> \
  --out evidence/demo-livrable1-<UTC>
```

La campagne du 30 octobre 2026 (commit testé `2f05504`, 29/29 contrôles) est conservée
dans `evidence/demo-livrable1-20261030T133958Z/`. Elle valide le protocole on-chain
sur réseaux locaux uniquement : ni le relayer .NET, ni PostgreSQL, ni le signataire,
ni Sepolia, ni TELA. Elle ne remplace pas une campagne `prove`.
