#!/usr/bin/env python3
"""Free-variable check for the engine's sources, with no external linter.

Why this exists: a missing import inside an error path is the worst kind of defect
here. `cli.main` had a crash handler that referenced a name it never imported, so
the code meant to guarantee "a fault never borrows a meaningful exit code" raised
`NameError` while trying to say so. Tests only catch that when the path is walked;
this walks every path statically.

Two findings, both reported by file and line:

* `undefined` — a name is loaded that nothing in the module binds and that is not a
  builtin. Locals bound inside the same function count as bound, so this is a check
  for unimported module-level references, not a full scope solver.
* `unused-import` — an imported name that is never loaded. Dead imports mislead a
  reader about what a module depends on.

Run standalone:  python3 scripts/adoption/tests/hygiene.py scripts/adoption/engine
"""

from __future__ import annotations

import ast
import builtins
import os
import sys

BUILTIN_NAMES = set(dir(builtins)) | {
    "__file__", "__name__", "__doc__", "__package__", "__spec__", "__loader__",
    "__builtins__", "__debug__", "__path__", "__version__",
}


class _Visitor(ast.NodeVisitor):
    def __init__(self):
        self.module_defs: set[str] = set()
        self.any_bound: set[str] = set()
        self.loads: dict[str, int] = {}
        self.imports: dict[str, int] = {}

    # -- bindings ----------------------------------------------------------
    def visit_Module(self, node: ast.Module) -> None:
        for child in node.body:
            self._module_level_bind(child)
        self.generic_visit(node)

    def _module_level_bind(self, node: ast.stmt) -> None:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.ImportFrom) and node.module == "__future__":
                return  # a compiler directive, never a loadable name
            for alias in node.names:
                name = (alias.asname or alias.name).split(".")[0]
                self.module_defs.add(name)
                self.imports[name] = node.lineno
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            self.module_defs.add(node.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            for target in self._targets(node):
                self.module_defs.add(target)
        elif isinstance(node, ast.Try):
            for sub in node.body + node.orelse + node.finalbody:
                self._module_level_bind(sub)
            for handler in node.handlers:
                self._module_level_bind(handler)

    def visit_FunctionDef(self, node) -> None:
        # A nested def and an import inside a function both bind names for that
        # function's body; treating them as undefined would bury the real findings.
        self.any_bound.add(node.name)
        self._bind_nested_imports(node)
        self._bind_args(node.args)
        self.generic_visit(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.any_bound.add(node.name)
        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                self.any_bound.add(child.name)
            elif isinstance(child, (ast.Assign, ast.AnnAssign)):
                for target in self._targets(child):
                    self.any_bound.add(target)
        self.generic_visit(node)

    def _bind_nested_imports(self, node: ast.AST) -> None:
        for sub in ast.walk(node):
            if isinstance(sub, (ast.Import, ast.ImportFrom)):
                for alias in sub.names:
                    self.any_bound.add((alias.asname or alias.name).split(".")[0])

    def visit_Lambda(self, node: ast.Lambda) -> None:
        self._bind_args(node.args)
        self.generic_visit(node)

    def _bind_args(self, args: ast.arguments) -> None:
        groups = [*args.posonlyargs, *args.args, *args.kwonlyargs]
        if args.vararg:
            groups.append(args.vararg)
        if args.kwarg:
            groups.append(args.kwarg)
        for arg in groups:
            self.any_bound.add(arg.arg)

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Store):
            self.any_bound.add(node.id)
        elif isinstance(node.ctx, ast.Del):
            self.any_bound.add(node.id)
        else:
            self.loads.setdefault(node.id, node.lineno)
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.name:
            self.any_bound.add(node.name)
        self.generic_visit(node)

    def visit_NamedExpr(self, node: ast.NamedExpr) -> None:
        if isinstance(node.target, ast.Name):
            self.any_bound.add(node.target.id)
        self.generic_visit(node)

    def visit_MatchAs(self, node: ast.MatchAs) -> None:
        if node.name:
            self.any_bound.add(node.name)
        self.generic_visit(node)

    def visit_MatchStar(self, node: ast.MatchStar) -> None:
        if node.name:
            self.any_bound.add(node.name)
        self.generic_visit(node)

    def visit_MatchMapping(self, node: ast.MatchMapping) -> None:
        if node.rest:
            self.any_bound.add(node.rest)
        self.generic_visit(node)

    @staticmethod
    def _targets(node):
        if isinstance(node, ast.AnnAssign):
            node = node.target
            stack = [node]
        elif isinstance(node, ast.AugAssign):
            stack = [node.target]
        else:
            stack = list(node.targets)
        while stack:
            target = stack.pop()
            if isinstance(target, ast.Name):
                yield target.id
            elif isinstance(target, (ast.Tuple, ast.List)):
                stack.extend(target.elts)


def analyze(source: str, filename: str = "<string>") -> dict:
    tree = ast.parse(source, filename=filename)
    visitor = _Visitor()
    visitor.visit(tree)
    undefined = sorted(
        (name, line)
        for name, line in visitor.loads.items()
        if name not in visitor.any_bound
        and name not in visitor.module_defs
        and name not in BUILTIN_NAMES
    )
    unused = sorted(
        (name, line)
        for name, line in visitor.imports.items()
        if name not in visitor.loads
    )
    return {"undefined": undefined, "unused-import": unused}


def check_paths(paths: list[str]) -> list[str]:
    problems: list[str] = []
    for path in paths:
        if os.path.isdir(path):
            files = [
                os.path.join(path, name)
                for name in sorted(os.listdir(path))
                if name.endswith(".py")
            ]
        else:
            files = [path]
        for file in files:
            with open(file, encoding="utf-8") as handle:
                try:
                    found = analyze(handle.read(), file)
                except SyntaxError as exc:
                    problems.append(f"{file}:{exc.lineno}: SyntaxError: {exc.msg}")
                    continue
            for kind, items in found.items():
                for name, line in items:
                    problems.append(f"{file}:{line}: {kind} {name!r}")
    return problems


if __name__ == "__main__":
    targets = sys.argv[1:] or ["scripts/adoption/engine"]
    found = check_paths(targets)
    for problem in found:
        print(problem)
    print(f"{len(found)} problem(s) in {len(targets)} path(s)")
    sys.exit(1 if found else 0)
