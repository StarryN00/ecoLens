"""H2 —— 导出 API 文档为 Markdown。

读取 FastAPI 的 OpenAPI schema(``app.openapi()``),生成
``docs/API_REFERENCE.md``。FastAPI 自带的在线 Swagger UI(``/docs``)
仍然可用;本脚本产出一份可随仓库归档、可离线查阅的静态 API 参考。

用法
----
    cd backend && python -m scripts.export_api_docs

只读取路由定义,不连真实数据库。
"""

from __future__ import annotations

import os
import sys
from datetime import datetime

# 导入 app 前补必填环境变量(只为拿到路由定义,占位值即可)
os.environ.setdefault("SECRET_KEY", "docs-export-placeholder-key")
os.environ.setdefault(
    "DATABASE_URL", "sqlite+aiosqlite:///./_docs_export.sqlite"
)
os.environ.setdefault(
    "CELERY_BROKER_URL", "sqla+sqlite:///./_docs_export_celery.sqlite"
)
os.environ.setdefault("CORS_ALLOWED_ORIGINS", "http://localhost")

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REPO_ROOT = os.path.dirname(_BACKEND_DIR)
sys.path.insert(0, _BACKEND_DIR)

from app.main import app  # noqa: E402

OUTPUT = os.path.join(_REPO_ROOT, "docs", "API_REFERENCE.md")

_HTTP_METHODS = ("get", "post", "put", "delete", "patch")


def _generate_markdown(schema: dict) -> str:
    info = schema.get("info", {})
    lines: list[str] = [
        f"# {info.get('title', 'API')} —— API 参考",
        "",
        f"- 版本:{info.get('version', '')}",
        f"- 生成时间:{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "> 本文件由 `backend/scripts/export_api_docs.py` 从 FastAPI "
        "OpenAPI schema 自动生成。",
        "> 在线交互式文档(可直接试调)见后端的 `/docs`(Swagger UI)。",
        "",
        "所有 `/api/v1/**` 接口除登录、注册外均需在请求头携带 "
        "`Authorization: Bearer <token>`。",
        "",
    ]

    # 按 tag 分组
    by_tag: dict[str, list[tuple[str, str, dict]]] = {}
    for path, methods in sorted(schema.get("paths", {}).items()):
        for method, op in methods.items():
            if method.lower() not in _HTTP_METHODS:
                continue
            tag = (op.get("tags") or ["其他"])[0]
            by_tag.setdefault(tag, []).append((method.upper(), path, op))

    for tag in sorted(by_tag):
        lines.append(f"## {tag}")
        lines.append("")
        for method, path, op in by_tag[tag]:
            lines.append(f"### `{method} {path}`")
            lines.append("")
            if op.get("summary"):
                lines.append(f"**{op['summary']}**")
                lines.append("")
            desc = (op.get("description") or "").strip()
            if desc:
                lines.append(desc.replace("\n", "  \n"))
                lines.append("")

            params = op.get("parameters") or []
            if params:
                lines.append("参数:")
                lines.append("")
                lines.append("| 名称 | 位置 | 必填 | 说明 |")
                lines.append("| --- | --- | --- | --- |")
                for p in params:
                    pdesc = (p.get("description") or "").replace("\n", " ")
                    required = "是" if p.get("required") else "否"
                    lines.append(
                        f"| {p.get('name')} | {p.get('in')} "
                        f"| {required} | {pdesc} |"
                    )
                lines.append("")

            responses = op.get("responses") or {}
            if responses:
                lines.append("响应:")
                lines.append("")
                for code in sorted(responses):
                    rdesc = responses[code].get("description", "")
                    lines.append(f"- `{code}` —— {rdesc}")
                lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    schema = app.openapi()
    markdown = _generate_markdown(schema)
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as fh:
        fh.write(markdown)
    endpoints = sum(
        1
        for methods in schema.get("paths", {}).values()
        for m in methods
        if m.lower() in _HTTP_METHODS
    )
    print(f"OK: 已生成 {OUTPUT}（{endpoints} 个接口）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
