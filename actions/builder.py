"""Autonomous, dependency-free web and app project builder actions."""
from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

from .fabric import ActionContext, ActionError, _safe_path
from .design import design_brief
from .website import _COLOR_RE, _NAME_RE, _required_text, website_create

_KINDS = {"website", "app"}
_MAX_PROJECT_BYTES = 5_000_000


def _kind(args: dict[str, Any]) -> str:
    value = str(args.get("kind", "website")).strip().lower()
    if value not in _KINDS:
        raise ActionError("kind must be website or app")
    return value


def _project(context: ActionContext, args: dict[str, Any]) -> Path:
    raw = args.get("project_dir", args.get("name", "site"))
    if not isinstance(raw, str) or not raw.strip():
        raise ActionError("project_dir is required")
    raw = raw.strip()
    if "/" in raw or "\\" in raw or raw in {".", ".."} or not _NAME_RE.fullmatch(raw):
        raise ActionError("project_dir must be one safe workspace-relative directory name")
    return _safe_path(context.workspace, raw)


def _app_files(name: str, title: str, description: str, accent: str, *, args: dict[str, Any]) -> dict[str, str]:
    safe_name = html.escape(name)
    safe_title = html.escape(title)
    safe_description = html.escape(description)
    brief = design_brief(args, kind="app")
    features = brief["features"]
    feature_markup = "".join([
        '<section class="feature"><h2>Calculator</h2><form id="calculator-form"><label>Units <input name="units" type="number" min="1" value="1" required></label><label>Rate <input name="rate" type="number" min="0" step="0.01" value="0" required></label><button type="submit">Calculate</button><p id="calculator-result" role="status"></p></form></section>' if "calculator" in features else "",
        '<section class="feature"><h2>Contact</h2><form id="contact-form"><label>Name <input name="name" required></label><label>Email <input name="email" type="email" required></label><label>Message <textarea name="message" required></textarea></label><button type="submit">Save message</button><p id="contact-result" role="status"></p></form></section>' if "contact_form" in features else "",
        '<section class="feature"><h2>Booking request</h2><form id="booking-form"><label>Date <input name="date" type="date" required></label><label>Time <input name="time" type="time" required></label><button type="submit">Save booking</button><p id="booking-result" role="status"></p></form></section>' if "booking" in features else "",
        '<section class="feature"><h2>Newsletter</h2><form id="newsletter-form"><label>Email <input name="email" type="email" required></label><button type="submit">Subscribe</button><p id="newsletter-result" role="status"></p></form></section>' if "newsletter" in features else "",
    ])
    feature_js = f'''\nconst features = {json.dumps(features)};
const saveFeature = (key, data) => {{ const current = JSON.parse(localStorage.getItem('aegis-app-features') || '[]'); current.unshift({{ key, data, createdAt: new Date().toISOString() }}); localStorage.setItem('aegis-app-features', JSON.stringify(current.slice(0, 100))); }};
const bind = (id, key, callback) => {{ const node = document.querySelector(id); if (!node || !features.includes(key)) return; node.addEventListener('submit', (event) => {{ event.preventDefault(); callback(node); }}); }};
bind('#calculator-form', 'calculator', (node) => {{ const data = Object.fromEntries(new FormData(node)); const total = (Number(data.units) * Number(data.rate)).toFixed(2); saveFeature('calculator', {{ ...data, total }}); node.querySelector('#calculator-result').textContent = `Estimated total: $${{total}}`; }});
bind('#contact-form', 'contact_form', (node) => {{ saveFeature('contact_form', Object.fromEntries(new FormData(node))); node.querySelector('#contact-result').textContent = 'Saved locally for this demonstration.'; node.reset(); }});
bind('#booking-form', 'booking', (node) => {{ saveFeature('booking', Object.fromEntries(new FormData(node))); node.querySelector('#booking-result').textContent = 'Booking request saved locally for this demonstration.'; node.reset(); }});
bind('#newsletter-form', 'newsletter', (node) => {{ saveFeature('newsletter', Object.fromEntries(new FormData(node))); node.querySelector('#newsletter-result').textContent = 'Subscription saved locally for this demonstration.'; node.reset(); }});
'''
    manifest = json.dumps(brief, indent=2, sort_keys=True)
    return {
        "index.html": f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="{accent}">
  <meta name="description" content="{safe_description}">
  <link rel="manifest" href="app.webmanifest">
  <link rel="stylesheet" href="styles.css">
  <title>{safe_title}</title>
</head>
<body>
  <main id="app" class="app-shell">
    <section class="app-card" aria-labelledby="app-title">
      <p class="eyebrow">AEGIS app starter</p>
      <h1 id="app-title">{safe_title}</h1>
      <p class="lede">{safe_description}</p>
      <form id="capture-form">
        <label for="capture-input">Add an item</label>
        <div class="input-row"><input id="capture-input" name="item" autocomplete="off" required><button type="submit">Add</button></div>
      </form>
      <ul id="items" aria-live="polite"></ul>
      {feature_markup}
    </section>
  </main>
  <script src="app.js" defer></script>
</body>
</html>
''',
        "styles.css": f''':root {{ --accent:{accent}; --ink:#17202a; --muted:#657180; --paper:#f7fafc; --line:#d7e0e8; }}
* {{ box-sizing:border-box; }} body {{ margin:0; min-width:320px; background:linear-gradient(145deg,#e7f3f7,#f7fafc 55%,#e9e6fa); color:var(--ink); font:16px/1.5 system-ui,sans-serif; }}
.app-shell {{ min-height:100vh; display:grid; place-items:center; padding:24px; }} .app-card {{ width:min(100%,760px); padding:clamp(28px,7vw,64px); border:1px solid rgba(23,32,42,.12); border-radius:24px; background:rgba(255,255,255,.86); box-shadow:0 22px 70px rgba(42,66,84,.16); }} .feature {{ margin-top:28px; padding-top:22px; border-top:1px solid var(--line); }} .feature form {{ display:grid; gap:10px; }} .feature textarea {{ width:100%; min-height:90px; }}
.eyebrow {{ color:var(--accent); font-size:.75rem; font-weight:800; letter-spacing:.14em; text-transform:uppercase; }} h1 {{ margin:10px 0; font-size:clamp(2.3rem,8vw,5rem); line-height:.98; }} .lede {{ color:var(--muted); }}
form {{ margin-top:30px; }} label {{ display:block; margin-bottom:8px; font-weight:700; }} .input-row {{ display:flex; gap:8px; }} input {{ min-width:0; flex:1; border:1px solid var(--line); border-radius:10px; padding:12px; font:inherit; }} button {{ border:0; border-radius:10px; background:var(--accent); color:#071017; padding:12px 18px; font-weight:800; cursor:pointer; }}
ul {{ display:grid; gap:8px; margin:26px 0 0; padding:0; list-style:none; }} li {{ border:1px solid var(--line); border-radius:10px; padding:10px 12px; background:var(--paper); }}
@media (max-width:520px) {{ .app-shell {{ padding:12px; }} .app-card {{ border-radius:18px; }} .input-row {{ flex-direction:column; }} }}
''',
        "app.js": '''const form = document.querySelector('#capture-form');
const input = document.querySelector('#capture-input');
const items = document.querySelector('#items');
const storageKey = 'aegis-app-items';
const saved = JSON.parse(localStorage.getItem(storageKey) || '[]');
function render() { items.replaceChildren(...saved.map((item) => { const li = document.createElement('li'); li.textContent = item; return li; })); }
form.addEventListener('submit', (event) => { event.preventDefault(); const value = input.value.trim(); if (!value) return; saved.unshift(value); localStorage.setItem(storageKey, JSON.stringify(saved.slice(0, 100))); input.value = ''; render(); });
render();
{feature_js}
''',
        "app.webmanifest": '{\n  "name": "' + safe_title + '",\n  "short_name": "' + safe_name + '",\n  "start_url": "./",\n  "display": "standalone",\n  "background_color": "#f7fafc",\n  "theme_color": "' + accent + '"\n}\n',
        "README.md": f'''# {name}\n\nGenerated by the AEGIS autonomous app builder.\n\n{title}\n\n{description}\n\nThis is a dependency-free installable web-app starter with local browser storage. Requested features: {', '.join(brief['feature_labels']) or 'none'}.\n\nFeature submissions stay in the browser for this demonstration. Connecting them to a production API, CRM, payments, or scheduling provider requires a separately authorized integration.\n''',
        "aegis.design.json": manifest + "\n",
    }


def project_create(context: ActionContext, args: dict[str, Any]) -> dict[str, Any]:
    """Create a website or dependency-free installable web app."""
    kind = _kind(args)
    if kind == "website":
        result = website_create(context, args)
        return {**result, "kind": kind, "stage": "create"}

    name = _required_text(args, "name", 64)
    if not _NAME_RE.fullmatch(name):
        raise ActionError("name contains unsupported characters")
    title = _required_text(args, "title", 120)
    description = _required_text(args, "description", 500)
    accent = args.get("accent", "#7dd3fc")
    if not isinstance(accent, str) or not _COLOR_RE.fullmatch(accent):
        raise ActionError("accent must be a six-digit hex color")
    project = _project(context, {**args, "name": name})
    existed = project.exists()
    if existed and not project.is_dir():
        raise ActionError("project_dir exists and is not a directory")
    if existed and any(project.iterdir()) and args.get("overwrite") is not True:
        raise ActionError("project_dir is not empty; set overwrite=true to update generated files")
    files = _app_files(name, title, description, accent, args=args)
    total = sum(len(value.encode("utf-8")) for value in files.values())
    if total > _MAX_PROJECT_BYTES:
        raise ActionError("generated project exceeds action size limit")
    project.mkdir(parents=True, exist_ok=True)
    for relative, content in files.items():
        _safe_path(project, relative).write_text(content, encoding="utf-8")
    return {"project_dir": str(project.relative_to(context.workspace.resolve())), "files": sorted(files), "total_bytes": total, "overwrote": existed, "kind": kind, "design": design_brief(args, kind=kind), "stage": "create"}


def project_build(context: ActionContext, args: dict[str, Any]) -> dict[str, Any]:
    """Validate that a generated project has a complete, contained artifact set."""
    kind = _kind(args)
    project = _project(context, args)
    expected = {"index.html", "styles.css", "README.md"}
    expected.add("script.js" if kind == "website" else "app.js")
    if kind == "app":
        expected.add("app.webmanifest")
    missing = sorted(path for path in expected if not (project / path).is_file())
    if missing:
        raise ActionError(f"build validation failed; missing files: {', '.join(missing)}")
    files = sorted(path.name for path in project.iterdir() if path.is_file())
    total = sum(path.stat().st_size for path in project.iterdir() if path.is_file())
    if total > _MAX_PROJECT_BYTES:
        raise ActionError("project exceeds build size limit")
    return {"project_dir": str(project.relative_to(context.workspace.resolve())), "kind": kind, "files": files, "total_bytes": total, "build_mode": "dependency-free artifact validation", "stage": "build", "passed": True}


def project_test(context: ActionContext, args: dict[str, Any]) -> dict[str, Any]:
    """Run deterministic static checks against a generated project."""
    kind = _kind(args)
    project = _project(context, args)
    index = (project / "index.html").read_text(encoding="utf-8") if (project / "index.html").is_file() else ""
    checks = {
        "doctype": index.lower().startswith("<!doctype html>"),
        "viewport": 'name="viewport"' in index,
        "title": bool(re.search(r"<title>.+?</title>", index, re.I | re.S)),
        "semantic_main": bool(re.search(r"<main\b", index, re.I)),
        "local_assets": not bool(re.search(r"(?:src|href)=\"https?://", index, re.I)),
        "no_eval": "eval(" not in (project / ("script.js" if kind == "website" else "app.js")).read_text(encoding="utf-8"),
    }
    if kind == "app":
        checks["manifest"] = (project / "app.webmanifest").is_file()
        checks["form_label"] = 'for="capture-input"' in index
    checks["design_manifest"] = (project / "aegis.design.json").is_file()
    failed = sorted(name for name, passed in checks.items() if not passed)
    if failed:
        raise ActionError(f"self-test failed: {', '.join(failed)}")
    return {"project_dir": str(project.relative_to(context.workspace.resolve())), "kind": kind, "checks": checks, "stage": "test", "passed": True}


def builder_run(context: ActionContext, args: dict[str, Any]) -> dict[str, Any]:
    """Run create, build, and test as one autonomous governed action."""
    created = project_create(context, args)
    built = project_build(context, args)
    tested = project_test(context, args)
    return {"status": "PASS", "kind": created["kind"], "project_dir": created["project_dir"], "design": created["design"], "stages": [created, built, tested], "evidence": {"files": built["files"], "checks": tested["checks"]}}
