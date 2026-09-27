"""Deterministic repository intelligence for AEGIS coding agents.

Builds a compact architecture/symbol/import/test map, then selects task-relevant
files before model reasoning. This prevents large repositories from being
understood only by whichever files happen to fit first in a context window.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

TEXT_SUFFIXES={".py",".js",".jsx",".ts",".tsx",".mjs",".cjs",".json",".yml",".yaml",".toml",".md",".sh",".sql",".go",".rs",".java",".c",".h",".cpp",".hpp"}
CODE_SUFFIXES=TEXT_SUFFIXES-{".md",".json",".yml",".yaml",".toml"}
TOKEN_RE=re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")


@dataclass
class FileIntel:
    path:str
    size:int
    language:str
    symbols:list[str]
    imports:list[str]
    tests:bool
    entrypoint:bool


def _read(path:Path,limit:int=120_000)->str:
    try:return path.read_text(encoding="utf-8")[:limit]
    except (OSError,UnicodeDecodeError):return ""


def _python_intel(text:str)->tuple[list[str],list[str]]:
    try: tree=ast.parse(text)
    except SyntaxError:return [],[]
    symbols=[]; imports=[]
    for node in ast.walk(tree):
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)): symbols.append(node.name)
        elif isinstance(node,ast.Import): imports.extend(alias.name for alias in node.names)
        elif isinstance(node,ast.ImportFrom) and node.module: imports.append(node.module)
    return symbols[:200],imports[:200]


def _generic_intel(text:str)->tuple[list[str],list[str]]:
    symbols=re.findall(r"(?m)^(?:export\s+)?(?:async\s+)?(?:function|class|interface|type|const|let|var)\s+([A-Za-z_$][\w$]*)",text)
    imports=re.findall(r"(?:from\s+|require\(|import\s*\()['\"]([^'\"]+)",text)
    return list(dict.fromkeys(symbols))[:200],list(dict.fromkeys(imports))[:200]


def inspect_file(root:Path,name:str)->FileIntel|None:
    path=root/name
    if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:return None
    text=_read(path)
    if not text:return None
    symbols,imports=_python_intel(text) if path.suffix==".py" else _generic_intel(text)
    lower=name.lower()
    return FileIntel(name,len(text),path.suffix.lstrip(".") or "text",symbols,imports,
        bool(re.search(r"(^|/)(tests?|__tests__)/|(^|[._-])(test|spec)[._-]",lower)),
        path.name in {"main.py","app.py","server.py","index.ts","index.js","package.json","pyproject.toml","compose.yml"})


def build_repository_map(root:Path,files:Iterable[str])->list[FileIntel]:
    result=[]
    for name in files:
        item=inspect_file(root,name)
        if item:result.append(item)
    return result


def select_relevant(root:Path,inventory:list[FileIntel],objective:str,limit:int=28)->list[FileIntel]:
    terms={x.lower() for x in TOKEN_RE.findall(objective) if len(x)>2}
    scored=[]
    for item in inventory:
        hay=" ".join([item.path,*item.symbols,*item.imports]).lower()
        score=sum(5 for term in terms if term in item.path.lower())
        score+=sum(2 for term in terms if term in hay)
        score+=2 if item.entrypoint else 0
        score+=1 if item.tests else 0
        scored.append((score,item))
    primary=[item for score,item in sorted(scored,key=lambda x:(x[0],-x[1].size),reverse=True) if score>0][:limit]
    # Pull tests and directly referenced local modules around the primary set.
    stems={Path(x.path).stem.lower() for x in primary}
    neighbors=[x for x in inventory if x not in primary and (x.tests and any(s in x.path.lower() for s in stems))]
    selected=(primary+neighbors)[:limit]
    if not selected:
        selected=[x for x in inventory if x.entrypoint][:limit]
    if not selected:
        # Preserve the legacy snapshot contract for tiny repos, documentation-only
        # repos, and callers that do not provide an objective.
        selected=inventory[:limit]
    return selected


def architecture_context(root:Path,files:list[str],objective:str,max_chars:int=180_000)->str:
    inventory=build_repository_map(root,files)
    selected=select_relevant(root,inventory,objective)
    lines=["AEGIS REPOSITORY INTELLIGENCE",f"Tracked text/code files: {len(inventory)}",f"Task-focused files: {len(selected)}","\nRepository map:"]
    for item in inventory[:500]:
        flags=(" test" if item.tests else "")+(" entrypoint" if item.entrypoint else "")
        lines.append(f"- {item.path} [{item.language}{flags}] symbols={','.join(item.symbols[:12]) or '-'} imports={','.join(item.imports[:10]) or '-'}")
    lines.append("\nTask-focused source:")
    total=sum(len(x)+1 for x in lines)
    for item in selected:
        data=_read(root/item.path,60_000)
        if not data:continue
        remaining=max_chars-total
        if remaining<=1000:break
        chunk=f"\n--- {item.path} ---\n{data[:remaining]}"
        lines.append(chunk);total+=len(chunk)
    return "\n".join(lines)[:max_chars]
