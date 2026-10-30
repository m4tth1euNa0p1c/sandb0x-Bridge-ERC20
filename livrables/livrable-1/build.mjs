// Rendu HTML → PDF du livrable 1 (Chromium via Playwright, Mermaid local, aucun accès réseau).
// Usage : node build.mjs <sortie.pdf> [pages.json]
import { createRequire } from 'node:module';
import { readFileSync, readdirSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '../..');
const [output, pagesFile] = process.argv.slice(2);
if (!output) { console.error('Usage : node build.mjs <sortie.pdf> [pages.json]'); process.exit(2); }

const parts = readdirSync(join(here, 'src/parts')).filter(f => f.endsWith('.html')).sort();
const body = parts.map(f => readFileSync(join(here, 'src/parts', f), 'utf8')).join('\n');
const html = readFileSync(join(here, 'src/template.html'), 'utf8').replace('<!-- BODY -->', body);
const buildDir = join(here, 'build');
mkdirSync(buildDir, { recursive: true });
const page_ = join(buildDir, 'document.html');
writeFileSync(page_, html);

const mermaid = join(root, 'docs/assets/vendor/mermaid-11.16.1/mermaid.min.js');
const pages = pagesFile ? JSON.parse(readFileSync(pagesFile, 'utf8')) : {};

const browser = await chromium.launch();
try {
  const page = await browser.newPage();
  // Seuls les fichiers locaux sont autorisés.
  await page.route('**/*', route => route.request().url().startsWith('file://') ? route.continue() : route.abort());
  await page.goto(pathToFileURL(page_).href, { waitUntil: 'load' });
  await page.addScriptTag({ path: mermaid });
  const report = await page.evaluate(async (pages) => {
    // Les marges de page n'entraînent pas le chargement des polices : on charge toutes les graisses.
    await Promise.all(['400', '500', '600', '700', '800', 'italic 400'].flatMap(w =>
      [document.fonts.load(`${w} 12px InterDoc`, 'Aé'), document.fonts.load(`${w} 12px InterDoc`, 'ĀŒ')]));
    await document.fonts.ready;
    window.mermaid.initialize({
      startOnLoad: false, securityLevel: 'strict', theme: 'base', fontFamily: 'InterDoc, DejaVu Sans',
      themeVariables: {
        fontFamily: 'InterDoc, DejaVu Sans', fontSize: '13px', primaryColor: '#eff6ff', primaryBorderColor: '#1d4ed8',
        primaryTextColor: '#0f172a', lineColor: '#334155', secondaryColor: '#ecfeff', tertiaryColor: '#f8fafc',
        noteBkgColor: '#fffbeb', noteBorderColor: '#b45309', noteTextColor: '#0f172a',
        actorBkg: '#eff6ff', actorBorder: '#1d4ed8', signalColor: '#0f172a', signalTextColor: '#0f172a',
        labelBoxBkgColor: '#f1f5f9', labelBoxBorderColor: '#334155', sequenceNumberColor: '#ffffff',
        critBkgColor: '#fecaca', critBorderColor: '#b91c1c', doneTaskBkgColor: '#bbf7d0', taskBkgColor: '#bfdbfe',
        taskBorderColor: '#1d4ed8', activeTaskBkgColor: '#fde68a', sectionBkgColor: '#f8fafc', altSectionBkgColor: '#ffffff',
        gridColor: '#e2e8f0', todayLineColor: 'transparent'
      },
      flowchart: { htmlLabels: true, curve: 'basis', useMaxWidth: true, padding: 10 },
      sequence: { useMaxWidth: true, mirrorActors: false, showSequenceNumbers: true, boxMargin: 8, messageFontSize: 12, actorFontSize: 12, noteFontSize: 11.5, wrap: false, width: 120, actorMargin: 30, messageMargin: 30 },
      state: { useMaxWidth: true }, class: { useMaxWidth: true }, er: { useMaxWidth: true, fontSize: 12 },
      gantt: { useMaxWidth: true, useWidth: 680, barHeight: 18, barGap: 5, topPadding: 40, fontSize: 11, sectionFontSize: 11, leftPadding: 120, gridLineStartPadding: 30, numberSectionStyles: 2 }
    });
    const nodes = [...document.querySelectorAll('pre.mermaid')];
    const errors = [];
    for (const [i, node] of nodes.entries()) {
      try { await window.mermaid.run({ nodes: [node], suppressErrors: false }); }
      catch (e) { errors.push(`diagramme ${i + 1} : ${e.message || e}`); }
    }
    for (const svg of document.querySelectorAll('pre.mermaid svg')) {
      svg.removeAttribute('height');
      const fig = svg.closest('figure');
      if (fig?.dataset.maxw) svg.style.maxWidth = fig.dataset.maxw;
      svg.style.maxHeight = fig?.dataset.maxh || '205mm';
    }
    // Sommaire généré à partir des titres numérotés.
    const toc = document.getElementById('toc');
    const list = document.createElement('ol');
    let current = null;
    for (const h of document.querySelectorAll('main h1[id], main h2[id]')) {
      const num = h.querySelector('.num')?.textContent || '';
      const title = [...h.childNodes].filter(n => !(n.classList && n.classList.contains('num'))).map(n => n.textContent).join('').trim();
      const li = document.createElement('li');
      li.className = h.tagName === 'H1' ? 'l1' : 'l2';
      li.innerHTML = `<a href="#${h.id}"><span class="n">${num}</span><span class="t"></span><span class="p">${pages[h.id] ?? '00'}</span></a>`;
      li.querySelector('.t').textContent = title;
      if (h.tagName === 'H1') { list.append(li); current = document.createElement('ol'); li.append(current); }
      else (current || list).append(li);
    }
    toc.append(list);
    const missing = [...document.querySelectorAll('img')].filter(i => !i.complete || !i.naturalWidth).map(i => i.src);
    const outline = [...document.querySelectorAll('main h1[id], main h2[id]')].map(h => ({
      id: h.id, level: h.tagName === 'H1' ? 1 : 2, num: h.querySelector('.num')?.textContent || '',
      title: [...h.childNodes].filter(n => !(n.classList && n.classList.contains('num'))).map(n => n.textContent).join('').trim()
    }));
    return { diagrams: nodes.length, errors, missing, headings: outline.length, outline };
  }, pages);
  if (report.errors.length || report.missing.length) {
    console.error(JSON.stringify(report, null, 2));
    process.exit(1);
  }
  await page.pdf({ path: output, preferCSSPageSize: true, printBackground: true, outline: true, tagged: true });
  console.log(JSON.stringify(report));
} finally {
  await browser.close();
}
