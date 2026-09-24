"""Generate safe, category-aware demonstration pages from verified facts only."""
from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any

from actions.fabric import _safe_path

from .models import BusinessRecord, now


def slugify(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return value[:64] or "prospect"


def _escape(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def _category_copy(category: str) -> tuple[str, str]:
    lowered = category.lower()
    if any(token in lowered for token in ("restaurant", "bakery", "food", "cafe")):
        return "Make the next visit easy to choose.", "A focused local presence can put the essentials—what you offer, when you are open, and how to reach you—within one clear path."
    if any(token in lowered for token in ("auto", "repair", "vehicle")):
        return "A clearer path from problem to phone call.", "A practical service page can help local customers understand the business and take the next step without hunting for contact details."
    if any(token in lowered for token in ("salon", "barber", "beauty", "nail")):
        return "Make the next appointment feel simple.", "A polished mobile-first page can keep location, contact, and appointment intent close at hand."
    if any(token in lowered for token in ("contractor", "plumbing", "heating", "construction", "landscaping")):
        return "Turn local intent into a clear next step.", "A focused service-area page can help customers understand who to contact and how to start a conversation."
    return "A professional digital front door.", "A concise local page can make verified business information easier to find and act on."


def render_site(record: BusinessRecord) -> dict[str, str]:
    name = _escape(record.business_name)
    category = _escape(record.category or "Local business")
    address = _escape(record.address)
    phone = _escape(record.phone)
    hero, supporting = _category_copy(record.category)
    phone_link = re.sub(r"\D", "", record.phone)
    contact = f'<a class="button" href="tel:{_escape(phone_link)}">Call {name}</a>' if phone_link else '<a class="button" href="#contact">Get in touch</a>'
    location = f'<p><strong>Location</strong><br>{address}</p>' if address else ""
    phone_block = f'<p><strong>Phone</strong><br><a href="tel:{_escape(phone_link)}">{phone}</a></p>' if phone else ""
    return {
        "index.html": f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="Concept demonstration for {name}, a {category}.">
  <title>{name} · {category}</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <div class="concept-banner">PRIVATE CONCEPT DEMONSTRATION · NOT THE OFFICIAL BUSINESS WEBSITE</div>
  <header class="site-header"><a class="brand" href="#top">{name}</a><nav aria-label="Primary"><a href="#about">About</a><a href="#contact">Contact</a></nav></header>
  <main id="top">
    <section class="hero"><div class="hero-copy"><p class="eyebrow">{category}</p><h1>{_escape(hero)}</h1><p>{_escape(supporting)}</p>{contact}</div><div class="hero-card"><span>Verified public details</span>{location}{phone_block}</div></section>
    <section id="about" class="section split"><div><p class="eyebrow">WHY THIS CONCEPT</p><h2>Useful information, close to the customer.</h2></div><p>This demonstration uses only publicly verified details currently available to AEGIS. Services, prices, testimonials, awards, and guarantees are intentionally omitted until the business confirms them.</p></section>
    <section class="section cards"><article><span class="card-number">01</span><h3>Clear first impression</h3><p>Lead with the business category and a direct next step.</p></article><article><span class="card-number">02</span><h3>Local confidence</h3><p>Keep verified contact and location details visible on mobile.</p></article><article><span class="card-number">03</span><h3>Ready to extend</h3><p>Add confirmed services, booking, ordering, or gallery content after approval.</p></article></section>
    <section id="contact" class="section contact"><p class="eyebrow">CONTACT</p><h2>Ready when you are.</h2>{location}{phone_block}{contact}</section>
  </main>
  <footer>Concept prepared by AEGIS · Public facts only · {name}</footer>
  <script src="script.js" defer></script>
</body>
</html>
''',
        "styles.css": ''':root { --ink:#15211f; --muted:#5b6a66; --paper:#f5f1e9; --panel:#fffdf8; --accent:#d8754b; --line:#d9d6cc; }
* { box-sizing:border-box; } html { scroll-behavior:smooth; } body { margin:0; background:var(--paper); color:var(--ink); font:16px/1.6 Inter, ui-sans-serif, system-ui, sans-serif; }
a { color:inherit; text-decoration:none; } .concept-banner { background:var(--ink); color:#f9e9d6; padding:9px 5vw; text-align:center; font-size:10px; font-weight:800; letter-spacing:.12em; }
.site-header { display:flex; justify-content:space-between; align-items:center; max-width:1180px; margin:auto; padding:24px 5vw; } .brand { font-size:18px; font-weight:850; letter-spacing:-.03em; } nav { display:flex; gap:22px; color:var(--muted); font-size:13px; } nav a:hover { color:var(--accent); }
.hero { display:grid; grid-template-columns:minmax(0,1.35fr) minmax(260px,.65fr); align-items:end; gap:7vw; max-width:1180px; margin:auto; padding:104px 5vw 120px; } .eyebrow { color:var(--accent); font-size:11px; font-weight:850; letter-spacing:.14em; text-transform:uppercase; } h1 { max-width:760px; margin:14px 0 22px; font-size:clamp(3.1rem,8vw,7.5rem); line-height:.92; letter-spacing:-.075em; } h2 { margin:12px 0; font-size:clamp(2rem,4vw,4rem); line-height:1; letter-spacing:-.06em; } h3 { margin:12px 0 6px; font-size:20px; letter-spacing:-.03em; } .hero-copy > p:not(.eyebrow) { max-width:580px; color:var(--muted); font-size:18px; } .button { display:inline-block; margin-top:16px; border-radius:999px; background:var(--accent); color:#fff; padding:12px 18px; font-weight:800; } .button:hover { filter:brightness(.94); }
.hero-card { border:1px solid var(--line); border-radius:22px; background:var(--panel); padding:25px; box-shadow:0 22px 60px rgba(21,33,31,.08); } .hero-card > span { color:var(--accent); font-size:11px; font-weight:800; text-transform:uppercase; letter-spacing:.08em; } .hero-card p { margin:18px 0 0; color:var(--muted); } .hero-card strong { color:var(--ink); font-size:11px; text-transform:uppercase; letter-spacing:.08em; }
.section { max-width:1180px; margin:auto; padding:86px 5vw; } .split { display:grid; grid-template-columns:1fr 1fr; gap:8vw; border-top:1px solid var(--line); } .split > p { align-self:end; color:var(--muted); font-size:18px; } .cards { display:grid; grid-template-columns:repeat(3,1fr); gap:16px; } article { min-height:210px; border:1px solid var(--line); border-radius:18px; background:var(--panel); padding:24px; } article p { color:var(--muted); } .card-number { color:var(--accent); font-weight:850; }
.contact { border-top:1px solid var(--line); } .contact p:not(.eyebrow) { color:var(--muted); } footer { border-top:1px solid var(--line); color:var(--muted); padding:32px 5vw; text-align:center; font-size:12px; }
@media (max-width:760px) { .site-header { padding:18px 5vw; } nav { gap:12px; } .hero { display:block; padding-top:72px; } h1 { font-size:clamp(3rem,16vw,5rem); } .hero-card { margin-top:42px; } .split, .cards { grid-template-columns:1fr; } .section { padding:64px 5vw; } }
''',
        "script.js": "document.documentElement.dataset.ready = 'true';\n",
        "README.md": f'''# {record.business_name} — AEGIS concept\n\nThis is a private prospecting demonstration, not the official website of the business.\n\nGenerated at {now()} from verified public details only. Missing services, pricing, reviews, credentials, and claims are intentionally omitted pending business approval.\n''',
    }


def generate_demo(record: BusinessRecord, root: str | Path) -> dict[str, Any]:
    root_path = Path(root).resolve()
    project = _safe_path(root_path, slugify(record.business_name))
    if project.exists() and any(project.iterdir()):
        raise FileExistsError(f"demo directory is not empty: {project}")
    files = render_site(record)
    total = sum(len(content.encode("utf-8")) for content in files.values())
    if total > 5_000_000:
        raise ValueError("generated demo exceeds size limit")
    project.mkdir(parents=True, exist_ok=True)
    for relative, content in files.items():
        _safe_path(project, relative).write_text(content, encoding="utf-8")
    return {"project_dir": str(project), "relative_project_dir": str(project.relative_to(root_path)), "files": sorted(files), "total_bytes": total, "status": "generated"}
