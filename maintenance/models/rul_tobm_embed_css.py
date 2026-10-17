# -*- coding: utf-8 -*-
"""Embedded layout CSS for RUL & TOBM iframe (reference mockup v1.0.102 + inline v1111)."""

import re
from pathlib import Path

RUL_TOBM_EMBED_VERSION = "1.0.130"

_SCOPE = ".o_maint_rul_root"
_STATIC = Path(__file__).resolve().parent.parent / "static" / "src" / "views" / "rul_tobm_dashboard"

_IFRAME_SHELL = """
html, body.o_maint_rul_standalone_body {
    margin: 0;
    padding: 0;
    min-height: 100%;
    height: 100%;
    overflow-x: hidden;
    overflow-y: auto;
    background: #f8f9fa;
    font-family: "Segoe UI", system-ui, -apple-system, Roboto, sans-serif;
}
body.o_maint_rul_standalone_body .o_maint_rul_root {
    min-height: 100vh;
    width: 100%;
    max-width: 100%;
    box-sizing: border-box;
}
body.o_maint_rul_standalone_body .o_maint_rul_dashboard,
body.o_maint_rul_standalone_body .o_maint_rul_viewport {
    min-height: 100vh;
    width: 100%;
    max-width: 100%;
    box-sizing: border-box;
}
@keyframes o_maint_rul_pulse {
    0% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.45); }
    70% { box-shadow: 0 0 0 8px rgba(34, 197, 94, 0); }
    100% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0); }
}
.o_maint_rul_root .o_maint_rul_live_dot {
    animation: o_maint_rul_pulse 2s infinite;
}
.o_maint_rul_root .o_maint_rul_pill .fa-caret-down {
    margin-left: 2px;
    color: #94a3b8;
    font-size: 10px;
}
.o_maint_rul_root .o_maint_rul_legend {
    justify-content: center !important;
    padding: 0 !important;
    background: transparent !important;
    border: none !important;
}
.o_maint_rul_root .o_maint_rul_chart_wrap {
    flex: 1 1 auto !important;
    min-height: 0 !important;
    width: 100% !important;
    padding: 0 !important;
    margin: 0 !important;
    border: none !important;
    background: transparent !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    display: block !important;
}
.o_maint_rul_root .o_maint_rul_chart_svg {
    width: 100% !important;
    height: auto !important;
    min-height: 300px !important;
    aspect-ratio: 920 / 380 !important;
    display: block !important;
}
.o_maint_rul_root .o_maint_rul_card--detail {
    display: flex !important;
    flex-direction: column !important;
    flex: 1 1 auto !important;
    min-height: 0 !important;
}
.o_maint_rul_root .o_maint_rul_viewport {
    gap: 16px !important;
    padding: 16px 20px 14px !important;
    background: #f8f9fa !important;
}
.o_maint_rul_root .o_maint_rul_dashboard {
    background: #f8f9fa !important;
}
.o_maint_rul_root .o_maint_rul_header_text h1 {
    font-size: 24px !important;
}
.o_maint_rul_root .o_maint_rul_kpi_value {
    color: #0f172a !important;
}
.o_maint_rul_root .o_maint_rul_kpi--critical .o_maint_rul_kpi_value {
    color: #0f172a !important;
    font-size: 22px !important;
}
"""


def _load_mockup_css_from_js():
    js_path = _STATIC / "rul_tobm_inline_styles.js"
    if not js_path.is_file():
        return ""
    text = js_path.read_text(encoding="utf-8")
    marker = "export const RUL_TOBM_INLINE_CSS = `"
    start = text.find(marker)
    if start < 0:
        return ""
    start = text.find("`", start) + 1
    end = text.find("`;\n\nexport function ensureRulTobmInlineStyles", start)
    if end < 0:
        return ""
    return text[start:end].replace("${S}", _SCOPE)


def _scope_scss_file(path):
    if not path.is_file():
        return ""
    raw = path.read_text(encoding="utf-8")
    # Strip comments-only lines; scope each rule block under .o_maint_rul_root
    out = []
    for block in re.split(r"(?=/\*|\n(?=\.))", raw):
        block = block.strip()
        if not block or block.startswith("/*"):
            continue
        scoped = []
        for line in block.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("/*") or stripped.startswith("*"):
                continue
            if stripped.startswith("@"):
                scoped.append(line)
            elif stripped.startswith(".") and not stripped.startswith(_SCOPE):
                scoped.append(f"{_SCOPE} {line}")
            else:
                scoped.append(line)
        if scoped:
            out.append("\n".join(scoped))
    return "\n".join(out)


def _load_reference_mockup_scss():
    return _scope_scss_file(_STATIC / "rul_tobm_mockup.scss")


RUL_TOBM_EMBED_CSS = (
    _load_mockup_css_from_js()
    + "\n"
    + _load_reference_mockup_scss()
    + _IFRAME_SHELL
)
