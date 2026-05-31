from __future__ import annotations

import importlib.util

if importlib.util.find_spec("PyQt6") is None:
    raise RuntimeError("PyQt6 is required for the GUI. Install with: pip install -e '.[gui]'")

if importlib.util.find_spec("PyQt6.QtWebEngineWidgets") is not None:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    WEBENGINE_AVAILABLE = True
else:
    from PyQt6.QtWidgets import QTextEdit as QWebEngineView  # type: ignore
    WEBENGINE_AVAILABLE = False


MONACO_HTML = """
<!doctype html><html><head><meta charset='utf-8'>
<style>html,body,#container{margin:0;width:100%;height:100%;background:#1e1e1e;overflow:hidden}</style>
<script src="https://cdn.jsdelivr.net/npm/monaco-editor@0.49.0/min/vs/loader.js"></script>
</head><body><div id="container"></div><script>
let editor;
require.config({ paths: { vs: 'https://cdn.jsdelivr.net/npm/monaco-editor@0.49.0/min/vs' }});
require(['vs/editor/editor.main'], function () {
  monaco.editor.setTheme('vs-dark');
  editor = monaco.editor.create(document.getElementById('container'), {
    value: __CODE__, language: __LANG__, theme: 'vs-dark', automaticLayout: true,
    minimap: { enabled: true }, fontSize: 14
  });
});
</script></body></html>
"""


class MonacoEditor(QWebEngineView):  # type: ignore[misc]
    def set_code(self, code: str, language: str = "python") -> None:
        if WEBENGINE_AVAILABLE:
            page = MONACO_HTML.replace("__CODE__", repr(code)).replace("__LANG__", repr(language))
            self.setHtml(page)
        else:
            self.setPlainText(code)  # type: ignore[attr-defined]
            self.setStyleSheet("background:#1e1e1e;color:#d4d4d4;font-family:monospace;")


def language_for_path(path: str) -> str:
    suffix = path.rsplit(".", 1)[-1].lower() if "." in path else "txt"
    return {
        "py": "python",
        "js": "javascript",
        "ts": "typescript",
        "html": "html",
        "css": "css",
        "json": "json",
        "md": "markdown",
        "toml": "toml",
        "yaml": "yaml",
        "yml": "yaml",
    }.get(suffix, "plaintext")
