/* Adaptateur local des blocs fenced_code MkDocs. Aucun accès réseau. */
(() => {
  "use strict";

  async function renderDiagrams() {
    const blocks = [...document.querySelectorAll("pre > code.language-mermaid")];
    document.documentElement.dataset.mermaidExpected = String(blocks.length);
    let rendered = 0;
    let errors = 0;
    if (window.mermaid) {
      window.mermaid.initialize({
        startOnLoad: false,
        securityLevel: "strict",
        theme: "neutral",
        fontFamily: "Arial, Helvetica, sans-serif",
        flowchart: { htmlLabels: false, useMaxWidth: false },
        state: { useMaxWidth: false }
      });
    }
    for (const [index, code] of blocks.entries()) {
      const source = code.textContent;
      const original = code.parentElement;
      const figure = document.createElement("figure");
      figure.className = "bridge-diagram";
      const canvas = document.createElement("div");
      canvas.className = "bridge-diagram__canvas mermaid";
      canvas.setAttribute("aria-label", `Diagramme ${index + 1} ; défilement horizontal possible`);
      canvas.setAttribute("tabindex", "0");
      canvas.textContent = source;
      const details = document.createElement("details");
      const summary = document.createElement("summary");
      summary.textContent = "Source textuelle du diagramme";
      details.append(summary);
      original.replaceWith(figure);
      details.append(original);
      figure.append(canvas, details);
      try {
        if (!window.mermaid) throw new Error("mermaid_unavailable");
        await window.mermaid.run({ nodes: [canvas], suppressErrors: false });
        if (!canvas.querySelector("svg")) throw new Error("mermaid_svg_missing");
        canvas.dataset.mermaidResult = "rendered";
        rendered += 1;
      } catch (_error) {
        canvas.textContent = "Diagramme indisponible ; sa source textuelle reste accessible ci-dessous.";
        canvas.dataset.mermaidResult = "error";
        canvas.setAttribute("role", "alert");
        errors += 1;
      }
    }
    document.documentElement.dataset.mermaidRendered = String(rendered);
    document.documentElement.dataset.mermaidErrors = String(errors);
    document.documentElement.dataset.mermaidReady = "true";
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", renderDiagrams, { once: true });
  } else {
    void renderDiagrams();
  }
})();
