"""Governed static website project generation for AEGIS agents."""
from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

from .design import design_brief
from .fabric import ActionContext, ActionError, _safe_path

_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
_MAX_TOTAL_BYTES = 5_000_000


def _required_text(args: dict[str, Any], key: str, limit: int) -> str:
    value = args.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ActionError(f"{key} is required")
    value = value.strip()
    if len(value) > limit:
        raise ActionError(f"{key} exceeds {limit} characters")
    return value


def _project_dir(context: ActionContext, args: dict[str, Any]) -> Path:
    raw = args.get("project_dir", args.get("name", "site"))
    if not isinstance(raw, str) or not raw.strip():
        raise ActionError("project_dir is required")
    raw = raw.strip()
    if "/" in raw or "\\" in raw or raw in {".", ".."} or not _NAME_RE.fullmatch(raw):
        raise ActionError("project_dir must be a single workspace-relative directory name")
    return _safe_path(context.workspace, raw)


def _render(name: str, title: str, description: str, accent: str, *, args: dict[str, Any]) -> dict[str, str]:
    safe_name = html.escape(name)
    safe_title = html.escape(title)
    safe_description = html.escape(description)
    brief = design_brief(args, kind="website")
    features = brief["features"]
    feature_cards = "".join(
        f'<article><h3>{html.escape(label)}</h3><p>Designed as a verified {html.escape(label.lower())} module for this request.</p></article>'
        for label in brief["feature_labels"]
    )
    if not feature_cards:
        feature_cards = (
            '<article><h3>Fast</h3><p>A lightweight foundation with no external runtime dependencies.</p></article>'
            '<article><h3>Accessible</h3><p>Semantic structure, responsive layout, and keyboard-friendly navigation.</p></article>'
            '<article><h3>Auditable</h3><p>Every generated file is deterministic and contained inside the assigned workspace.</p></article>'
        )

    modules: list[str] = []
    if any(feature in features for feature in ("contact_form", "quote_request", "booking")):
        extra = (
            '<label>Date <input type="date" name="date" required></label>'
            '<label>Time <input type="time" name="time" required></label>'
            if "booking" in features else ""
        )
        purpose = "booking request" if "booking" in features else ("quote request" if "quote_request" in features else "message")
        modules.append(
            f'<section id="contact" class="section"><h2>Start a {purpose}</h2>'
            f'<form data-aegis-form="lead"><label>Name <input name="name" autocomplete="name" required></label>'
            f'<label>Email <input type="email" name="email" autocomplete="email" required></label>{extra}'
            f'<label>Details <textarea name="details" rows="4" required></textarea></label>'
            f'<button class="button" type="submit">Send request</button>'
            f'<p class="form-status" role="status" aria-live="polite"></p></form></section>'
        )
    if "newsletter" in features:
        modules.append(
            '<section id="newsletter" class="section"><h2>Keep in touch</h2>'
            '<form data-aegis-form="newsletter"><label>Email <input type="email" name="email" autocomplete="email" required></label>'
            '<button class="button" type="submit">Subscribe</button><p class="form-status" role="status" aria-live="polite"></p></form></section>'
        )
    if "faq" in features:
        modules.append(
            '<section id="faq" class="section"><h2>Questions</h2>'
            '<details><summary>What happens after I submit?</summary><p>Your request is saved in this private demonstration so the workflow can be tested without sending data anywhere.</p></details>'
            '<details><summary>Can this connect to a real system?</summary><p>A separately authorized backend, CRM, booking provider, or email capability can be connected after requirements are approved.</p></details></section>'
        )
    if "calculator" in features:
        modules.append(
            '<section id="calculator" class="section"><h2>Quick estimate</h2>'
            '<form data-aegis-form="calculator"><label>Units <input type="number" name="units" min="1" value="1" required></label>'
            '<label>Rate <input type="number" name="rate" min="0" step="0.01" value="0" required></label>'
            '<button class="button" type="submit">Calculate</button><p class="form-status" role="status" aria-live="polite"></p></form></section>'
        )

    manifest = json.dumps(brief, indent=2, sort_keys=True)
    return {
        "index.html": f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="{safe_description}">
  <title>{safe_title}</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <header class="site-header"><a class="brand" href="#top">{safe_name}</a><nav aria-label="Primary"><a href="#features">Features</a><a href="#about">About</a></nav></header>
  <main id="top">
    <section class="hero"><p class="eyebrow">Generated by AEGIS</p><h1>{safe_title}</h1><p>{safe_description}</p><a class="button" href="#features">Explore</a></section>
    <section id="features" class="section"><h2>Built to move forward</h2><div class="grid">{feature_cards}</div></section>
    <section id="about" class="section"><h2>About this project</h2><p>{safe_description}</p></section>
    {''.join(modules)}
  </main>
  <footer>Generated by AEGIS · <span id="year"></span></footer>
  <script src="script.js" defer></script>
</body>
</html>
''',
        "styles.css": f''':root {{ --accent: {accent}; --bg: #0b0d10; --panel: #13171c; --text: #f5f7fa; --muted: #aab2bd; }}
* {{ box-sizing: border-box; }} html {{ scroll-behavior: smooth; }} body {{ margin: 0; background: var(--bg); color: var(--text); font: 16px/1.6 system-ui, sans-serif; }}
a {{ color: inherit; text-decoration: none; }} .site-header {{ display:flex; justify-content:space-between; align-items:center; padding:24px 6vw; border-bottom:1px solid #252a31; }}
.brand {{ font-weight:800; letter-spacing:.04em; }} nav {{ display:flex; gap:24px; color:var(--muted); }} nav a:hover {{ color:var(--text); }}
.hero {{ min-height:68vh; display:grid; align-content:center; max-width:900px; margin:auto; padding:80px 6vw; }} .eyebrow {{ color:var(--accent); font-weight:700; text-transform:uppercase; letter-spacing:.14em; }}
h1 {{ font-size:clamp(3rem,9vw,7rem); line-height:.95; margin:12px 0 28px; max-width:850px; }} .hero p:not(.eyebrow) {{ color:var(--muted); font-size:1.2rem; max-width:680px; }}
.button {{ display:inline-block; width:max-content; margin-top:18px; padding:12px 20px; border:0; border-radius:10px; background:var(--accent); color:#050505; font:inherit; font-weight:800; cursor:pointer; }}
.section {{ max-width:1100px; margin:auto; padding:80px 6vw; }} .section h2 {{ font-size:2.2rem; }} .grid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:20px; }} article {{ background:var(--panel); border:1px solid #252a31; border-radius:16px; padding:28px; }} article p, .section > p, .form-status {{ color:var(--muted); }}
form {{ display:grid; gap:14px; max-width:640px; }} label {{ display:grid; gap:6px; font-weight:700; }} input, textarea {{ width:100%; border:1px solid #39424d; border-radius:10px; padding:12px; background:#0f1318; color:var(--text); font:inherit; }} details {{ border-top:1px solid #252a31; padding:18px 0; }} summary {{ cursor:pointer; font-weight:700; }}
footer {{ padding:40px 6vw; border-top:1px solid #252a31; color:var(--muted); }}
@media (max-width:700px) {{ .site-header {{ padding:18px 5vw; }} nav {{ gap:12px; }} .hero {{ min-height:60vh; padding:60px 5vw; }} .section {{ padding:60px 5vw; }} .grid {{ grid-template-columns:1fr; }} }}
''',
        "script.js": '''const year = document.getElementById('year');
if (year) year.textContent = new Date().getFullYear();
const storageKey = 'aegis-site-submissions';
for (const form of document.querySelectorAll('[data-aegis-form]')) {
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(form).entries());
    if (form.dataset.aegisForm === 'calculator') data.total = (Number(data.units) * Number(data.rate)).toFixed(2);
    const saved = JSON.parse(localStorage.getItem(storageKey) || '[]');
    saved.unshift({ type: form.dataset.aegisForm, data, createdAt: new Date().toISOString() });
    localStorage.setItem(storageKey, JSON.stringify(saved.slice(0, 100)));
    const status = form.querySelector('.form-status');
    if (status) status.textContent = form.dataset.aegisForm === 'calculator' ? `Estimated total: $${data.total}` : 'Saved locally for this demonstration.';
    if (form.dataset.aegisForm !== 'calculator') form.reset();
  });
}
''',
        "README.md": f'''# {name}

Generated by the AEGIS Website Builder.

## Project

{title}

{description}

Requested functions: {', '.join(brief['feature_labels']) or 'none'}.

The generated form, booking, newsletter, and calculator actions persist only in this browser demonstration. A production email, CRM, scheduling, payment, or authenticated data integration requires a separately authorized capability.
''',
        "aegis.design.json": manifest + "\n",
    }


def website_create(context: ActionContext, args: dict[str, Any]) -> dict[str, Any]:
    """Create a deterministic static website inside the assigned workspace."""
    name = _required_text(args, "name", 64)
    if not _NAME_RE.fullmatch(name):
        raise ActionError("name contains unsupported characters")
    title = _required_text(args, "title", 120)
    description = _required_text(args, "description", 500)
    accent = args.get("accent", "#7dd3fc")
    if not isinstance(accent, str) or not _COLOR_RE.fullmatch(accent):
        raise ActionError("accent must be a six-digit hex color")

    project = _project_dir(context, {**args, "name": name})
    project_exists = project.exists()
    if project_exists and not project.is_dir():
        raise ActionError("project_dir exists and is not a directory")
    if project_exists and any(project.iterdir()) and args.get("overwrite") is not True:
        raise ActionError("project_dir is not empty; set overwrite=true to update generated files")

    files = _render(name, title, description, accent, args=args)
    total = sum(len(content.encode("utf-8")) for content in files.values())
    if total > _MAX_TOTAL_BYTES:
        raise ActionError("generated project exceeds action size limit")

    project.mkdir(parents=True, exist_ok=True)
    for relative, content in files.items():
        _safe_path(project, relative).write_text(content, encoding="utf-8")

    return {
        "project_dir": str(project.relative_to(context.workspace.resolve())),
        "files": sorted(files),
        "total_bytes": total,
        "overwrote": project_exists,
        "design": design_brief(args, kind="website"),
    }
