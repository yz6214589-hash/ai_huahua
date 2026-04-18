import ast
import html
import io
import os
import re
import sys
import tokenize
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple


ROOT = os.path.abspath(os.path.dirname(__file__))

IGNORE_DIRS = {
    ".git",
    "__pycache__",
    "env_lianghua",
    "venv",
    ".venv",
    "outputs",
    "data",
    ".openclaw",
}

GENERATOR_TAG = "ai_huahua-py2html-docs"


def _read_text(path: str) -> str:
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            with open(path, "r", encoding=enc, errors="strict") as f:
                return f.read()
        except Exception:
            continue
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _write_text(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def _is_main_if(node: ast.AST) -> bool:
    if not isinstance(node, ast.If):
        return False
    test = node.test
    if not isinstance(test, ast.Compare):
        return False
    if not isinstance(test.left, ast.Name) or test.left.id != "__name__":
        return False
    if len(test.ops) != 1 or not isinstance(test.ops[0], ast.Eq):
        return False
    if len(test.comparators) != 1:
        return False
    c = test.comparators[0]
    if isinstance(c, ast.Constant) and c.value == "__main__":
        return True
    if isinstance(c, ast.Str) and c.s == "__main__":
        return True
    return False


def _unparse(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        return node.__class__.__name__


def _format_args(args: ast.arguments) -> str:
    parts: List[str] = []
    posonly = getattr(args, "posonlyargs", [])
    for a in posonly:
        parts.append(a.arg)
    if posonly:
        parts.append("/")
    for a in args.args:
        parts.append(a.arg)
    if args.vararg is not None:
        parts.append("*" + args.vararg.arg)
    elif args.kwonlyargs:
        parts.append("*")
    for a in args.kwonlyargs:
        parts.append(a.arg)
    if args.kwarg is not None:
        parts.append("**" + args.kwarg.arg)
    return ", ".join(parts)


def _collect_calls(node: ast.AST) -> List[str]:
    calls: List[str] = []
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            try:
                calls.append(_unparse(n.func))
            except Exception:
                calls.append("call")
    return calls


def _collect_try_handlers(tree: ast.AST) -> List[str]:
    out: List[str] = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Try):
            for h in n.handlers:
                if h.type is None:
                    out.append("except: (裸捕获)")
                else:
                    out.append(f"except {_unparse(h.type)}")
    return out


def _collect_imports(tree: ast.AST) -> List[str]:
    imports: List[str] = []
    for n in tree.body if isinstance(tree, ast.Module) else []:
        if isinstance(n, ast.Import):
            for a in n.names:
                if a.asname:
                    imports.append(f"import {a.name} as {a.asname}")
                else:
                    imports.append(f"import {a.name}")
        elif isinstance(n, ast.ImportFrom):
            mod = "." * (n.level or 0) + (n.module or "")
            names = []
            for a in n.names:
                names.append(f"{a.name} as {a.asname}" if a.asname else a.name)
            imports.append(f"from {mod} import {', '.join(names)}")
    return imports


@dataclass
class FunctionInfo:
    name: str
    signature: str
    decorators: List[str]
    doc: str
    calls: List[str]


@dataclass
class ClassInfo:
    name: str
    bases: List[str]
    methods: List[FunctionInfo]
    doc: str


def _collect_defs(tree: ast.Module) -> Tuple[List[FunctionInfo], List[ClassInfo], List[str]]:
    funcs: List[FunctionInfo] = []
    classes: List[ClassInfo] = []
    main_blocks: List[str] = []

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            decos = [_unparse(d) for d in node.decorator_list]
            sig = f"{node.name}({_format_args(node.args)})"
            funcs.append(
                FunctionInfo(
                    name=node.name,
                    signature=sig,
                    decorators=decos,
                    doc=ast.get_docstring(node) or "",
                    calls=_collect_calls(node),
                )
            )
        elif isinstance(node, ast.ClassDef):
            methods: List[FunctionInfo] = []
            for b in node.body:
                if isinstance(b, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    decos = [_unparse(d) for d in b.decorator_list]
                    sig = f"{b.name}({_format_args(b.args)})"
                    methods.append(
                        FunctionInfo(
                            name=b.name,
                            signature=sig,
                            decorators=decos,
                            doc=ast.get_docstring(b) or "",
                            calls=_collect_calls(b),
                        )
                    )
            bases = [_unparse(b) for b in node.bases]
            classes.append(
                ClassInfo(
                    name=node.name,
                    bases=bases,
                    methods=methods,
                    doc=ast.get_docstring(node) or "",
                )
            )
        elif _is_main_if(node):
            main_blocks.append("if __name__ == '__main__': ...")

    return funcs, classes, main_blocks


KEYWORDS = set(__import__("keyword").kwlist)


def _token_class(tok_type: int, tok_str: str) -> str:
    if tok_type == tokenize.COMMENT:
        return "tok-comment"
    if tok_type == tokenize.STRING:
        return "tok-string"
    if tok_type == tokenize.NUMBER:
        return "tok-number"
    if tok_type == tokenize.NAME and tok_str in KEYWORDS:
        return "tok-keyword"
    if tok_type == tokenize.NAME:
        return "tok-name"
    if tok_type == tokenize.OP:
        return "tok-op"
    return "tok-other"


def _highlight_python(code: str) -> str:
    out: List[str] = []
    try:
        tokens = tokenize.generate_tokens(io.StringIO(code).readline)
        for tok_type, tok_str, _, _, _ in tokens:
            esc = html.escape(tok_str)
            if tok_str.strip() == "":
                out.append(esc)
            else:
                cls = _token_class(tok_type, tok_str)
                out.append(f'<span class="{cls}">{esc}</span>')
        return "".join(out)
    except Exception:
        return html.escape(code)


CSS = """
  body { margin: 0; font-family: "Microsoft YaHei","PingFang SC",Arial,sans-serif; background: #f5f7fb; color: #111827; line-height: 1.75; }
  .container { max-width: 1080px; margin: 24px auto; background: #fff; border: 1px solid #e5e7eb; border-radius: 12px; padding: 24px 28px; box-shadow: 0 8px 24px rgba(2, 6, 23, 0.06); }
  h1 { margin: 0 0 10px; font-size: 24px; }
  h2 { margin: 24px 0 10px; font-size: 18px; border-left: 4px solid #3b82f6; padding-left: 10px; }
  h3 { margin: 16px 0 8px; font-size: 16px; }
  .meta { background: #f8fafc; border: 1px dashed #cbd5e1; border-radius: 8px; padding: 10px 12px; }
  .pill { display: inline-block; background: #dbeafe; border: 1px solid #bfdbfe; color: #1e40af; border-radius: 999px; padding: 2px 10px; margin: 0 8px 8px 0; font-size: 12px; }
  code.inline { background: #eef2ff; color: #1e3a8a; padding: 2px 6px; border-radius: 6px; }
  pre { background: #0b1020; color: #e5e7eb; padding: 14px; border-radius: 10px; overflow-x: auto; }
  pre code { font-family: Consolas, "JetBrains Mono", "Fira Code", monospace; font-size: 12.5px; }
  table { width: 100%; border-collapse: collapse; margin-top: 10px; }
  th, td { border: 1px solid #e5e7eb; padding: 8px 10px; text-align: left; vertical-align: top; }
  th { background: #f8fafc; }
  ul { padding-left: 20px; }
  .tok-keyword { color: #93c5fd; font-weight: 600; }
  .tok-string { color: #86efac; }
  .tok-comment { color: #94a3b8; font-style: italic; }
  .tok-number { color: #fca5a5; }
  .tok-name { color: #e2e8f0; }
  .tok-op { color: #cbd5e1; }
  .tok-other { color: #e2e8f0; }
"""


def _html_for_file(py_path: str, code: str) -> str:
    rel_path = os.path.relpath(py_path, ROOT).replace("\\", "/")
    try:
        tree = ast.parse(code, filename=py_path)
    except Exception as e:
        tree = ast.Module(body=[], type_ignores=[])
        parse_error = str(e)
    else:
        parse_error = ""

    module_doc = ""
    if isinstance(tree, ast.Module):
        module_doc = ast.get_docstring(tree) or ""

    imports = _collect_imports(tree) if isinstance(tree, ast.Module) else []
    funcs, classes, main_blocks = _collect_defs(tree) if isinstance(tree, ast.Module) else ([], [], [])
    handlers = _collect_try_handlers(tree)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    highlighted = _highlight_python(code)

    parts: List[str] = []
    parts.append("<!DOCTYPE html>")
    parts.append('<html lang="zh-CN">')
    parts.append("<head>")
    parts.append('  <meta charset="UTF-8" />')
    parts.append('  <meta name="viewport" content="width=device-width, initial-scale=1.0" />')
    parts.append(f'  <meta name="generator" content="{GENERATOR_TAG}" />')
    parts.append(f'  <meta name="generated-at" content="{html.escape(now)}" />')
    parts.append(f'  <meta name="source-path" content="{html.escape(rel_path)}" />')
    parts.append(f"  <title>{html.escape(os.path.basename(py_path))} 代码逻辑梳理</title>")
    parts.append("  <style>")
    parts.append(CSS)
    parts.append("  </style>")
    parts.append("</head>")
    parts.append("<body>")
    parts.append('  <div class="container">')
    parts.append(f"    <h1>{html.escape(os.path.basename(py_path))}</h1>")
    parts.append('    <div class="meta">')
    parts.append(f'      <span class="pill">源文件：{html.escape(rel_path)}</span>')
    parts.append(f'      <span class="pill">生成时间：{html.escape(now)}</span>')
    parts.append("    </div>")

    parts.append("    <section>")
    parts.append("      <h2>文件概述</h2>")
    if module_doc.strip():
        parts.append(f"      <pre><code>{html.escape(module_doc.strip())}</code></pre>")
    else:
        parts.append("      <p>未检测到模块级文档字符串。</p>")
    if parse_error:
        parts.append("      <h3>语法解析异常</h3>")
        parts.append(f"      <pre><code>{html.escape(parse_error)}</code></pre>")
    parts.append("    </section>")

    parts.append("    <section>")
    parts.append("      <h2>依赖关系（导入）</h2>")
    if imports:
        parts.append("      <ul>")
        for imp in imports:
            parts.append(f"        <li><code class=\"inline\">{html.escape(imp)}</code></li>")
        parts.append("      </ul>")
    else:
        parts.append("      <p>未检测到顶层 import/from import。</p>")
    parts.append("    </section>")

    parts.append("    <section>")
    parts.append("      <h2>类定义（类图）</h2>")
    if classes:
        parts.append("      <table>")
        parts.append("        <thead><tr><th>类</th><th>继承</th><th>方法</th></tr></thead>")
        parts.append("        <tbody>")
        for c in classes:
            bases = ", ".join(c.bases) if c.bases else "-"
            methods = ", ".join(m.name for m in c.methods) if c.methods else "-"
            parts.append(f"          <tr><td><code class=\"inline\">{html.escape(c.name)}</code></td><td>{html.escape(bases)}</td><td>{html.escape(methods)}</td></tr>")
        parts.append("        </tbody>")
        parts.append("      </table>")
        parts.append("      <h3>类说明</h3>")
        parts.append("      <ul>")
        for c in classes:
            if c.doc.strip():
                parts.append(f"        <li><code class=\"inline\">{html.escape(c.name)}</code>：{html.escape(c.doc.strip())}</li>")
        parts.append("      </ul>")
    else:
        parts.append("      <p>未检测到类定义。</p>")
    parts.append("    </section>")

    parts.append("    <section>")
    parts.append("      <h2>函数与方法</h2>")
    if funcs or any(c.methods for c in classes):
        if funcs:
            parts.append("      <h3>模块级函数</h3>")
            parts.append("      <ul>")
            for f in funcs:
                parts.append(f"        <li><code class=\"inline\">{html.escape(f.signature)}</code></li>")
            parts.append("      </ul>")
        for c in classes:
            if not c.methods:
                continue
            parts.append(f"      <h3>类 {html.escape(c.name)} 的方法</h3>")
            parts.append("      <ul>")
            for m in c.methods:
                parts.append(f"        <li><code class=\"inline\">{html.escape(m.signature)}</code></li>")
            parts.append("      </ul>")
    else:
        parts.append("      <p>未检测到函数/方法定义。</p>")
    parts.append("    </section>")

    parts.append("    <section>")
    parts.append("      <h2>函数调用链（静态分析）</h2>")
    if funcs or any(c.methods for c in classes):
        parts.append("      <table>")
        parts.append("        <thead><tr><th>作用域</th><th>调用点（可能包含库函数/对象方法）</th></tr></thead>")
        parts.append("        <tbody>")
        for f in funcs:
            calls = ", ".join(dict.fromkeys(f.calls)) if f.calls else "-"
            parts.append(f"          <tr><td><code class=\"inline\">{html.escape(f.name)}</code></td><td>{html.escape(calls)}</td></tr>")
        for c in classes:
            for m in c.methods:
                calls = ", ".join(dict.fromkeys(m.calls)) if m.calls else "-"
                parts.append(f"          <tr><td><code class=\"inline\">{html.escape(c.name + '.' + m.name)}</code></td><td>{html.escape(calls)}</td></tr>")
        parts.append("        </tbody>")
        parts.append("      </table>")
        parts.append("      <p>说明：该调用链为语法树静态扫描结果，未做跨文件符号解析与动态分派推断。</p>")
    else:
        parts.append("      <p>无可用的函数/方法调用信息。</p>")
    parts.append("    </section>")

    parts.append("    <section>")
    parts.append("      <h2>主流程</h2>")
    if main_blocks:
        parts.append("      <ul>")
        for b in main_blocks:
            parts.append(f"        <li><code class=\"inline\">{html.escape(b)}</code></li>")
        parts.append("      </ul>")
    else:
        parts.append("      <p>未检测到 <code class=\"inline\">if __name__ == '__main__'</code> 主入口。</p>")
    parts.append("    </section>")

    parts.append("    <section>")
    parts.append("      <h2>异常处理</h2>")
    if handlers:
        parts.append("      <ul>")
        for h in handlers:
            parts.append(f"        <li><code class=\"inline\">{html.escape(h)}</code></li>")
        parts.append("      </ul>")
    else:
        parts.append("      <p>未检测到 try/except 结构。</p>")
    parts.append("    </section>")

    parts.append("    <section>")
    parts.append("      <h2>源码（语法高亮）</h2>")
    parts.append("      <pre><code>")
    parts.append(highlighted)
    parts.append("      </code></pre>")
    parts.append("    </section>")

    parts.append("  </div>")
    parts.append("</body>")
    parts.append("</html>")

    return "\n".join(parts) + "\n"


def _should_overwrite(html_path: str) -> bool:
    if not os.path.exists(html_path):
        return True
    try:
        head = _read_text(html_path)[:4000]
    except Exception:
        return True
    return (f'name=\"generator\" content=\"{GENERATOR_TAG}\"' in head) or (GENERATOR_TAG in head)


def iter_py_files(root: str) -> List[str]:
    paths: List[str] = []
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in IGNORE_DIRS]
        for fn in fns:
            if fn.lower().endswith(".py"):
                paths.append(os.path.join(dp, fn))
    paths.sort()
    return paths


def main() -> int:
    py_files = iter_py_files(ROOT)
    total = len(py_files)
    generated = 0
    skipped = 0
    failed: List[Tuple[str, str]] = []

    for p in py_files:
        html_path = os.path.splitext(p)[0] + ".html"
        if not _should_overwrite(html_path):
            skipped += 1
            continue
        try:
            code = _read_text(p)
            doc = _html_for_file(p, code)
            _write_text(html_path, doc)
            generated += 1
        except Exception as e:
            failed.append((p, str(e)))

    print(f"PY_FILES={total}")
    print(f"GENERATED={generated}")
    print(f"SKIPPED_EXISTING={skipped}")
    print(f"FAILED={len(failed)}")
    if failed:
        print("FAILED_FILES:")
        for p, msg in failed[:50]:
            print(f"- {os.path.relpath(p, ROOT)} :: {msg}")
        if len(failed) > 50:
            print(f"... and {len(failed) - 50} more")

    return 0 if not failed else 2


if __name__ == "__main__":
    raise SystemExit(main())

