"""
Backend static audit (best-effort).

Goals:
- Enumerate module-level defs (functions, async functions, classes, class methods).
- Build a best-effort reference graph using static import patterns:
  - from x import y as alias  -> alias usage => reference to x.y
  - import x as alias         -> alias.attr usage => reference to x.attr
- Detect intra-module references via direct calls: foo() where foo is a module-level function.
- Flag potential duplicate implementations by hashing normalized AST for function bodies.

IMPORTANT LIMITATIONS (by design):
- Python is dynamic; this script only sees *static* references and common import forms.
- It cannot reliably detect getattr/dynamic import/call-by-string patterns.
- Use results as "candidates to review", not as a delete list.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]  # repo root
BACKEND_APP = ROOT / "backend" / "app"


def _to_module_name(py_path: Path) -> str:
  rel = py_path.relative_to(BACKEND_APP).with_suffix("")
  parts = ["app"] + list(rel.parts)
  return ".".join(parts)


def _sha1(s: str) -> str:
  return hashlib.sha1(s.encode("utf-8")).hexdigest()


@dataclass
class DefInfo:
  module: str
  file: str
  kind: str  # function | async_function | class | method
  name: str
  qualname: str
  lineno: int
  signature: str | None = None
  body_hash: str | None = None


@dataclass
class ModuleInfo:
  module: str
  file: str
  parse_error: str | None = None
  defs: list[DefInfo] = field(default_factory=list)
  # alias -> fully qualified symbol, e.g. "foo" -> "app.utils.jwt_token.decode"
  imported_name_aliases: dict[str, str] = field(default_factory=dict)
  # alias -> module, e.g. "jwt" -> "app.utils.jwt_token"
  imported_module_aliases: dict[str, str] = field(default_factory=dict)
  # references: fully qualified symbol -> count
  refs: dict[str, int] = field(default_factory=dict)


def _iter_py_files(base: Path) -> list[Path]:
  out: list[Path] = []
  for p in base.rglob("*.py"):
    if "__pycache__" in p.parts:
      continue
    out.append(p)
  return sorted(out)


def _format_signature(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
  def fmt_arg(a: ast.arg) -> str:
    return a.arg

  args = []
  for a in fn.args.posonlyargs:
    args.append(fmt_arg(a))
  if fn.args.posonlyargs:
    args.append("/")
  for a in fn.args.args:
    args.append(fmt_arg(a))
  if fn.args.vararg:
    args.append("*" + fn.args.vararg.arg)
  elif fn.args.kwonlyargs:
    args.append("*")
  for a in fn.args.kwonlyargs:
    args.append(fmt_arg(a))
  if fn.args.kwarg:
    args.append("**" + fn.args.kwarg.arg)
  return f"{fn.name}({', '.join(args)})"


def _hash_function_body(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
  # Normalize using AST dump without attributes; include the body only.
  node = ast.Module(body=fn.body, type_ignores=[])
  dumped = ast.dump(node, include_attributes=False)
  return _sha1(dumped)


class _Visitor(ast.NodeVisitor):
  def __init__(self, mi: ModuleInfo, module_level_functions: set[str]):
    self.mi = mi
    self.module_level_functions = module_level_functions
    # local direct call tracking
    self._local_calls: dict[str, int] = {}

  def visit_ImportFrom(self, node: ast.ImportFrom) -> Any:
    mod = node.module
    if not mod:
      return
    for a in node.names:
      if a.name == "*":
        continue
      alias = a.asname or a.name
      self.mi.imported_name_aliases[alias] = f"{mod}.{a.name}"
    self.generic_visit(node)

  def visit_Import(self, node: ast.Import) -> Any:
    for a in node.names:
      # We only reliably handle "import x.y as alias" (or "import x as alias").
      # "import x.y" binds name "x", which is hard to resolve statically here.
      if a.asname:
        self.mi.imported_module_aliases[a.asname] = a.name
      else:
        # keep a conservative mapping for "import x"
        self.mi.imported_module_aliases[a.name.split(".")[0]] = a.name.split(".")[0]
    self.generic_visit(node)

  def visit_Call(self, node: ast.Call) -> Any:
    # local direct call: foo(...)
    fn = node.func
    if isinstance(fn, ast.Name):
      name = fn.id
      if name in self.module_level_functions:
        self._local_calls[name] = self._local_calls.get(name, 0) + 1
    self.generic_visit(node)

  def visit_Name(self, node: ast.Name) -> Any:
    # imported name alias usage
    sym = self.mi.imported_name_aliases.get(node.id)
    if sym:
      self.mi.refs[sym] = self.mi.refs.get(sym, 0) + 1
    self.generic_visit(node)

  def visit_Attribute(self, node: ast.Attribute) -> Any:
    # module alias attribute usage: alias.attr
    if isinstance(node.value, ast.Name):
      base = node.value.id
      mod = self.mi.imported_module_aliases.get(base)
      if mod and node.attr:
        sym = f"{mod}.{node.attr}"
        self.mi.refs[sym] = self.mi.refs.get(sym, 0) + 1
    self.generic_visit(node)

  def finalize(self) -> None:
    # record local calls as fully qualified "module.func"
    for name, n in self._local_calls.items():
      sym = f"{self.mi.module}.{name}"
      self.mi.refs[sym] = self.mi.refs.get(sym, 0) + n


def _parse_module(py_path: Path) -> ModuleInfo:
  mod = _to_module_name(py_path)
  mi = ModuleInfo(module=mod, file=str(py_path.relative_to(ROOT)))
  try:
    src = py_path.read_text(encoding="utf-8")
    tree = ast.parse(src, filename=str(py_path))
  except Exception as e:  # noqa: BLE001 (best-effort tool)
    mi.parse_error = f"{type(e).__name__}: {e}"
    return mi

  module_level_functions: set[str] = set()

  # Collect defs (module-level)
  for node in tree.body:
    if isinstance(node, ast.FunctionDef):
      module_level_functions.add(node.name)
      mi.defs.append(
        DefInfo(
          module=mi.module,
          file=mi.file,
          kind="function",
          name=node.name,
          qualname=f"{mi.module}.{node.name}",
          lineno=getattr(node, "lineno", 0),
          signature=_format_signature(node),
          body_hash=_hash_function_body(node),
        )
      )
    elif isinstance(node, ast.AsyncFunctionDef):
      module_level_functions.add(node.name)
      mi.defs.append(
        DefInfo(
          module=mi.module,
          file=mi.file,
          kind="async_function",
          name=node.name,
          qualname=f"{mi.module}.{node.name}",
          lineno=getattr(node, "lineno", 0),
          signature=_format_signature(node),
          body_hash=_hash_function_body(node),
        )
      )
    elif isinstance(node, ast.ClassDef):
      mi.defs.append(
        DefInfo(
          module=mi.module,
          file=mi.file,
          kind="class",
          name=node.name,
          qualname=f"{mi.module}.{node.name}",
          lineno=getattr(node, "lineno", 0),
        )
      )
      for b in node.body:
        if isinstance(b, ast.FunctionDef):
          mi.defs.append(
            DefInfo(
              module=mi.module,
              file=mi.file,
              kind="method",
              name=b.name,
              qualname=f"{mi.module}.{node.name}.{b.name}",
              lineno=getattr(b, "lineno", 0),
              signature=_format_signature(b),
              body_hash=_hash_function_body(b),
            )
          )
        elif isinstance(b, ast.AsyncFunctionDef):
          mi.defs.append(
            DefInfo(
              module=mi.module,
              file=mi.file,
              kind="method",
              name=b.name,
              qualname=f"{mi.module}.{node.name}.{b.name}",
              lineno=getattr(b, "lineno", 0),
              signature=_format_signature(b),
              body_hash=_hash_function_body(b),
            )
          )

  # Collect references (best effort)
  v = _Visitor(mi, module_level_functions)
  v.visit(tree)
  v.finalize()
  return mi


def audit() -> dict[str, Any]:
  files = _iter_py_files(BACKEND_APP)
  modules: list[ModuleInfo] = [_parse_module(p) for p in files]

  # Build reverse reference map: target -> {referrer_module: count}
  ref_by_target: dict[str, dict[str, int]] = {}
  for mi in modules:
    for sym, n in mi.refs.items():
      ref_by_target.setdefault(sym, {})
      ref_by_target[sym][mi.module] = ref_by_target[sym].get(mi.module, 0) + n

  # Duplicate candidates by function body hash (module-level only)
  hash_to_defs: dict[str, list[DefInfo]] = {}
  for mi in modules:
    for d in mi.defs:
      if d.kind not in {"function", "async_function"}:
        continue
      if not d.body_hash:
        continue
      hash_to_defs.setdefault(d.body_hash, []).append(d)

  duplicates = []
  for h, defs in hash_to_defs.items():
    if len(defs) < 2:
      continue
    # group only if names match or very small function (still useful)
    duplicates.append(
      {
        "bodyHash": h,
        "count": len(defs),
        "defs": [
          {
            "qualname": d.qualname,
            "file": d.file,
            "lineno": d.lineno,
            "signature": d.signature,
          }
          for d in defs
        ],
      }
    )

  # Top-level def reference summary
  defs_summary = []
  for mi in modules:
    for d in mi.defs:
      if d.kind not in {"function", "async_function", "class"}:
        continue
      refs = ref_by_target.get(d.qualname, {})
      defs_summary.append(
        {
          "qualname": d.qualname,
          "kind": d.kind,
          "file": d.file,
          "lineno": d.lineno,
          "signature": d.signature,
          "referencedByModules": sorted(refs.keys()),
          "refCountTotal": sum(refs.values()),
        }
      )

  parse_errors = [
    {"module": mi.module, "file": mi.file, "error": mi.parse_error} for mi in modules if mi.parse_error
  ]

  return {
    "meta": {
      "repoRoot": str(ROOT),
      "backendAppDir": str(BACKEND_APP),
      "pythonFiles": len(files),
      "modulesParsed": sum(1 for m in modules if not m.parse_error),
      "modulesWithErrors": len(parse_errors),
    },
    "parseErrors": parse_errors,
    "modules": [
      {
        "module": mi.module,
        "file": mi.file,
        "parseError": mi.parse_error,
        "defs": [
          {
            "kind": d.kind,
            "name": d.name,
            "qualname": d.qualname,
            "lineno": d.lineno,
            "signature": d.signature,
          }
          for d in mi.defs
        ],
      }
      for mi in modules
    ],
    "defsSummary": defs_summary,
    "duplicates": sorted(duplicates, key=lambda x: x["count"], reverse=True),
  }


def write_reports(out_dir: Path) -> None:
  out_dir.mkdir(parents=True, exist_ok=True)
  data = audit()

  (out_dir / "backend_static_audit.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

  # Markdown summary
  md = []
  md.append("# Backend Static Audit (best-effort)\n")
  md.append("## Meta\n")
  meta = data["meta"]
  md.append(f"- python files: **{meta['pythonFiles']}**\n")
  md.append(f"- modules parsed: **{meta['modulesParsed']}**\n")
  if meta["modulesWithErrors"]:
    md.append(f"- modules with parse errors: **{meta['modulesWithErrors']}**\n")
  else:
    md.append("- modules with parse errors: **0**\n")

  if data["parseErrors"]:
    md.append("\n## Parse Errors\n")
    for e in data["parseErrors"][:50]:
      md.append(f"- `{e['file']}`: {e['error']}\n")
    if len(data["parseErrors"]) > 50:
      md.append(f"- (truncated) total: {len(data['parseErrors'])}\n")

  # Candidates: defs with 0 static refs (excluding obvious entrypoint modules)
  md.append("\n## Candidates (0 static references)\n")
  md.append("> 注意：仅表示“静态扫描未发现引用”；Python 动态特性可能导致漏检。\n\n")
  zero = [d for d in data["defsSummary"] if d["refCountTotal"] == 0]
  for d in zero[:200]:
    md.append(f"- `{d['qualname']}` ({d['kind']}) — `{d['file']}:{d['lineno']}`\n")
  if len(zero) > 200:
    md.append(f"- (truncated) total: {len(zero)}\n")

  md.append("\n## Duplicate Function Body Candidates (module-level)\n")
  md.append("> 依据：函数 body 的 AST hash 相同（不含注释/行号）。需要人工确认语义是否可合并。\n\n")
  if not data["duplicates"]:
    md.append("- none\n")
  else:
    for grp in data["duplicates"][:50]:
      md.append(f"- bodyHash `{grp['bodyHash']}` — **{grp['count']}** occurrences\n")
      for x in grp["defs"][:10]:
        md.append(f"  - `{x['qualname']}` — `{x['file']}:{x['lineno']}`\n")
      if len(grp["defs"]) > 10:
        md.append(f"  - (truncated) {len(grp['defs'])} total\n")

  (out_dir / "backend_static_audit.md").write_text("".join(md), encoding="utf-8")


if __name__ == "__main__":
  out = ROOT / "specs" / "lhmy-2.0-maintenance" / "reports"
  write_reports(out)
  print(f"Wrote reports to: {out}")


