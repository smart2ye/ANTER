"""يولّد وثائق reference/ من الكود مباشرة.

التشغيل:
    python3 scripts/generate_reference.py

يُحدّث:
    - routes.md
    - models.md
    - templates.md
    - services.md
    - README.md
"""
import os
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "app"
DOCS = ROOT / "docs" / "reference"

# نضمن أن جذر المشروع في sys.path ليستورد app
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TODAY = date.today().isoformat()


def ensure_docs_dir():
    DOCS.mkdir(parents=True, exist_ok=True)


def scan_registered_prefixes():
    """يقرأ prefixes من app/routes/__init__.py (register_blueprint)."""
    init_file = APP / "routes" / "__init__.py"
    if not init_file.exists():
        return {}
    src = init_file.read_text(encoding="utf-8", errors="ignore")
    result = {}
    for m in re.finditer(
        r"register_blueprint\(\s*(\w+)(?:\s*,\s*url_prefix\s*=\s*['\"]([^'\"]*)['\"])?",
        src,
    ):
        var, prefix = m.group(1), m.group(2) or ""
        result[var] = prefix
    return result


def scan_routes():
    """يمر على app/routes/*.py ويستخرج blueprints + routes."""
    routes_dir = APP / "routes"
    blueprints = []
    routes = []
    for py in sorted(routes_dir.glob("*.py")):
        if py.name.startswith("_"):
            continue
        src = py.read_text(encoding="utf-8", errors="ignore")
        bp_names = re.findall(r"(\w+)\s*=\s*Blueprint\(['\"](\w+)['\"]", src)
        for var, name in bp_names:
            prefix_match = re.search(
                rf"{var}\s*=\s*Blueprint\([^)]*url_prefix\s*=\s*['\"]([^'\"]*)['\"]",
                src,
            )
            prefix = prefix_match.group(1) if prefix_match else ""
            blueprints.append({"var": var, "name": name, "prefix": prefix, "file": py.name})

        for m in re.finditer(
            r"@(\w+)_bp\.route\(\s*['\"]([^'\"]+)['\"](?:\s*,\s*methods\s*=\s*\[([^\]]+)\])?",
            src,
        ):
            bp_var, path, methods = m.group(1), m.group(2), m.group(3)
            method_list = (
                [x.strip().strip("'\"") for x in methods.split(",")] if methods else ["GET"]
            )
            routes.append({
                "bp": bp_var,
                "path": path,
                "methods": method_list,
                "file": py.name,
            })
    return blueprints, routes


def scan_models():
    """يقرأ النماذج مع أعمدة كل جدول عبر SQLAlchemy inspect."""
    try:
        from app import create_app
        from app.extensions import db
        from sqlalchemy import inspect as sa_inspect

        app = create_app()
        with app.app_context():
            inspector = sa_inspect(db.engine)
            models = []
            for mapper in db.Model.registry.mappers:
                cls = mapper.class_
                if not cls.__module__.startswith("app.models"):
                    continue
                table = cls.__tablename__
                try:
                    cols = inspector.get_columns(table)
                except Exception:
                    cols = []
                columns = []
                for c in cols:
                    typ = str(c.get("type", ""))
                    nullable = c.get("nullable", True)
                    columns.append({
                        "name": c.get("name", ""),
                        "type": typ,
                        "nullable": nullable,
                        "pk": False,
                    })
                # أضف معرفة PK
                try:
                    pk = inspector.get_pk_constraint(table) or {}
                    pk_cols = pk.get("constrained_columns", []) or []
                    for col in columns:
                        if col["name"] in pk_cols:
                            col["pk"] = True
                except Exception:
                    pass
                models.append({
                    "class": cls.__name__,
                    "table": table,
                    "file": cls.__module__.split(".")[-1] + ".py",
                    "columns": columns,
                })
            models.sort(key=lambda m: m["class"])
            return models
    except Exception as e:
        print(f"  تحذير: تعذر قراءة الأعمدة ({e}) — نستخدم regex بديلًا")
        # fallback
        models_dir = APP / "models"
        models = []
        for py in sorted(models_dir.glob("*.py")):
            if py.name.startswith("_"):
                continue
            src = py.read_text(encoding="utf-8", errors="ignore")
            for m in re.finditer(r"class\s+(\w+)\s*\(([^)]*)\)", src):
                cls, bases = m.group(1), m.group(2)
                if "db.Model" not in bases and "Model" not in bases:
                    continue
                tn = re.search(rf"class\s+{cls}\b[\s\S]{{0,2000}}?__tablename__\s*=\s*['\"]([^'\"]+)", src)
                models.append({
                    "class": cls,
                    "table": tn.group(1) if tn else cls.lower(),
                    "file": py.name,
                    "columns": [],
                })
        return models


def scan_templates():
    tpl_dir = APP / "templates"
    templates = []
    for tpl in sorted(tpl_dir.rglob("*.html")):
        rel = tpl.relative_to(tpl_dir).as_posix()
        src = tpl.read_text(encoding="utf-8", errors="ignore")
        extends = re.search(r"{%\s*extends\s+['\"]([^'\"]+)['\"]", src)
        templates.append({
            "path": rel,
            "extends": extends.group(1) if extends else "",
        })
    return templates


def scan_services():
    svc_dir = APP / "services"
    services = []
    for py in sorted(svc_dir.glob("*.py")):
        if py.name.startswith("_"):
            continue
        src = py.read_text(encoding="utf-8", errors="ignore")
        # دوال مستقلة
        funcs = re.findall(r"^def\s+(\w+)\s*\(", src, re.MULTILINE)
        # دوال داخل class (بمسافة بادئة 4)
        methods = re.findall(r"^    def\s+(\w+)\s*\(", src, re.MULTILINE)
        classes = re.findall(r"^class\s+(\w+)", src, re.MULTILINE)
        services.append({
            "file": py.name,
            "functions": funcs,
            "methods": methods,
            "classes": classes,
        })
    return services


def write(path, content):
    (DOCS / path).write_text(content, encoding="utf-8")
    print(f"  - {path}")


def generate():
    ensure_docs_dir()
    blueprints, routes = scan_routes()
    models = scan_models()
    templates = scan_templates()
    services = scan_services()

    # routes.md
    lines = [
        "# مرجع المسارات (Routes)",
        "",
        f"**آخر تحديث:** {TODAY}",
        f"**المجموع:** {len(routes)} route · {len(blueprints)} blueprint",
        "",
    ]
    # خرائط الـ prefix — من routes/__init__.py أولاً
    registered = scan_registered_prefixes()
    prefix_map = {}
    for bp in blueprints:
        var = bp["var"]
        prefix = registered.get(var, bp.get("prefix", ""))
        # خزّن بمفتاحين: كامل (admin_bp) ومختصر (admin)
        prefix_map[var] = prefix
        if var.endswith("_bp"):
            prefix_map[var[:-3]] = prefix

    by_bp = {}
    for r in routes:
        by_bp.setdefault(r["bp"], []).append(r)
    for bp in sorted(by_bp.keys()):
        prefix = prefix_map.get(bp, "")
        lines.append(f"## {bp}" + (f" — `{prefix}`" if prefix else ""))
        lines.append("")
        for r in sorted(by_bp[bp], key=lambda x: x["path"]):
            methods = ",".join(r["methods"])
            full_path = (prefix.rstrip("/") + "/" + r["path"].lstrip("/")).rstrip("/") or "/"
            lines.append(f"- `{methods}` `{full_path}` — _{r['file']}_")
        lines.append("")
    write("routes.md", "\n".join(lines))

    # models.md
    lines = [
        "# مرجع النماذج (Models)",
        "",
        f"**آخر تحديث:** {TODAY}",
        f"**المجموع:** {len(models)} موديل",
        "",
    ]
    for m in models:
        lines.append(f"## {m['class']}")
        lines.append("")
        lines.append(f"- **الجدول:** `{m['table']}`")
        lines.append(f"- **الملف:** `{m['file']}`")
        cols = m.get("columns", [])
        if cols:
            lines.append("")
            lines.append("| العمود | النوع | Nullable | PK |")
            lines.append("|---|---|---|---|")
            for c in cols:
                pk_mark = "✓" if c["pk"] else ""
                null_mark = "✓" if c["nullable"] else ""
                lines.append(f"| `{c['name']}` | {c['type']} | {null_mark} | {pk_mark} |")
        lines.append("")
    write("models.md", "\n".join(lines))

    # templates.md
    lines = [
        "# مرجع القوالب (Templates)",
        "",
        f"**آخر تحديث:** {TODAY}",
        f"**المجموع:** {len(templates)} قالب",
        "",
        "| المسار | يمتد من |",
        "|---|---|",
    ]
    for t in templates:
        lines.append(f"| `{t['path']}` | {t['extends'] or '—'} |")
    write("templates.md", "\n".join(lines))

    # services.md
    lines = [
        "# مرجع الخدمات (Services)",
        "",
        f"**آخر تحديث:** {TODAY}",
        f"**المجموع:** {len(services)} خدمة",
        "",
    ]
    for s in services:
        lines.append(f"## {s['file']}")
        lines.append("")
        if s.get("classes"):
            lines.append(f"**الفئات:** {', '.join(s['classes'])}")
            lines.append("")
        if s["functions"]:
            lines.append("**دوال مستقلة:**")
            for fn in s["functions"]:
                lines.append(f"- `{fn}()`")
            lines.append("")
        if s.get("methods"):
            lines.append("**دوال الفئات (methods):**")
            for m in s["methods"]:
                lines.append(f"- `.{m}()`")
            lines.append("")
    write("services.md", "\n".join(lines))

    # README.md
    lines = [
        "# فهرس مرجع ANTER",
        "",
        f"**آخر تحديث:** {TODAY}",
        "",
        "## الملفات",
        f"- routes.md — المسارات ({len(routes)} route · {len(blueprints)} blueprint)",
        f"- models.md — النماذج ({len(models)} موديل)",
        f"- templates.md — القوالب ({len(templates)} قالب)",
        f"- services.md — الخدمات ({len(services)} خدمة)",
        "- integrations.md — التكاملات الخارجية (يدوي)",
        "- identity.md — الهوية البصرية (يدوي)",
        "- ANTER_REFERENCE.md — نظرة شاملة (يدوي)",
        "",
        "## التوليد",
        "",
        "```bash",
        "python3 scripts/generate_reference.py",
        "```",
    ]
    write("README.md", "\n".join(lines))

    print(f"\n✔ اكتمل: {len(routes)} route · {len(models)} model · {len(templates)} template · {len(services)} service")


if __name__ == "__main__":
    generate()
