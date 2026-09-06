#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MD Reader - jednoduchá, ale pekná čítačka Markdown súborov pre Windows.

Funkcie:
  * Renderovanie Markdownu do HTML v štýle GitHubu (QWebEngineView).
  * Zvýrazňovanie syntaxe v blokoch kódu (Pygments).
  * Bočný panel so zoznamom .md súborov v priečinku.
  * Svetlá / tmavá téma (prepínač + zapamätanie voľby).
  * Automatické znovunačítanie pri zmene súboru na disku.
  * Otvorenie súboru cez argument príkazového riadka (asociácia .md).
"""

import os
import sys

import markdown
from PySide6.QtCore import Qt, QFileSystemWatcher, QSettings, QUrl, QTimer
from PySide6.QtGui import QAction, QDesktopServices, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QSplitter,
    QWidget,
    QVBoxLayout,
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEnginePage

APP_NAME = "MD Reader"
ORG_NAME = "MDReader"


# --------------------------------------------------------------------------- #
#  CSS témy (GitHub-like)                                                      #
# --------------------------------------------------------------------------- #

BASE_CSS = """
* { box-sizing: border-box; }
html, body {
    margin: 0;
    padding: 0;
    font-family: -apple-system, "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    font-size: 16px;
    line-height: 1.6;
    -webkit-font-smoothing: antialiased;
}
.markdown-body {
    max-width: 900px;
    margin: 0 auto;
    padding: 40px 48px 80px 48px;
    word-wrap: break-word;
}
.markdown-body h1, .markdown-body h2 {
    padding-bottom: .3em;
    border-bottom: 1px solid var(--border);
    margin-top: 1.5em;
}
.markdown-body h1 { font-size: 2em; }
.markdown-body h2 { font-size: 1.5em; }
.markdown-body h3 { font-size: 1.25em; margin-top: 1.4em; }
.markdown-body h1:first-child,
.markdown-body h2:first-child,
.markdown-body h3:first-child { margin-top: 0; }
.markdown-body a { color: var(--link); text-decoration: none; }
.markdown-body a:hover { text-decoration: underline; }
.markdown-body code {
    font-family: "Cascadia Code", "Consolas", "SFMono-Regular", monospace;
    font-size: 85%;
    background: var(--code-inline-bg);
    padding: .2em .4em;
    border-radius: 6px;
}
.markdown-body pre {
    background: var(--code-bg);
    padding: 16px;
    border-radius: 8px;
    overflow: auto;
    line-height: 1.45;
}
.markdown-body pre code {
    background: transparent;
    padding: 0;
    font-size: 90%;
}
.markdown-body blockquote {
    margin: 0;
    padding: 0 1em;
    color: var(--muted);
    border-left: .25em solid var(--border);
}
.markdown-body table {
    border-collapse: collapse;
    width: 100%;
    margin: 1em 0;
    display: block;
    overflow: auto;
}
.markdown-body th, .markdown-body td {
    border: 1px solid var(--border);
    padding: 6px 13px;
}
.markdown-body tr:nth-child(2n) { background: var(--table-alt); }
.markdown-body img { max-width: 100%; }
.markdown-body hr { height: 1px; background: var(--border); border: 0; margin: 24px 0; }
.markdown-body ul.task-list { list-style: none; padding-left: 1em; }
.markdown-body kbd {
    background: var(--code-inline-bg);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 2px 6px;
    font-size: 85%;
}
"""

LIGHT_VARS = """
:root {
    --bg: #ffffff;
    --fg: #1f2328;
    --muted: #656d76;
    --link: #0969da;
    --border: #d0d7de;
    --code-bg: #f6f8fa;
    --code-inline-bg: rgba(175,184,193,.2);
    --table-alt: #f6f8fa;
}
body { background: var(--bg); color: var(--fg); }
"""

DARK_VARS = """
:root {
    --bg: #0d1117;
    --fg: #e6edf3;
    --muted: #8b949e;
    --link: #4493f8;
    --border: #30363d;
    --code-bg: #161b22;
    --code-inline-bg: rgba(110,118,129,.4);
    --table-alt: #161b22;
}
body { background: var(--bg); color: var(--fg); }
"""

# Pygments zvýraznenie kódu – jednoduché farby pre svetlú/tmavú tému
PYGMENTS_LIGHT = """
.codehilite .k, .codehilite .kd, .codehilite .kn { color: #cf222e; }
.codehilite .s, .codehilite .s1, .codehilite .s2, .codehilite .sb { color: #0a3069; }
.codehilite .c, .codehilite .c1, .codehilite .cm { color: #6e7781; font-style: italic; }
.codehilite .n { color: #1f2328; }
.codehilite .nf, .codehilite .fm { color: #8250df; }
.codehilite .mi, .codehilite .mf, .codehilite .m { color: #0550ae; }
.codehilite .o, .codehilite .ow { color: #cf222e; }
.codehilite .nb, .codehilite .bp { color: #0550ae; }
"""

PYGMENTS_DARK = """
.codehilite .k, .codehilite .kd, .codehilite .kn { color: #ff7b72; }
.codehilite .s, .codehilite .s1, .codehilite .s2, .codehilite .sb { color: #a5d6ff; }
.codehilite .c, .codehilite .c1, .codehilite .cm { color: #8b949e; font-style: italic; }
.codehilite .n { color: #e6edf3; }
.codehilite .nf, .codehilite .fm { color: #d2a8ff; }
.codehilite .mi, .codehilite .mf, .codehilite .m { color: #79c0ff; }
.codehilite .o, .codehilite .ow { color: #ff7b72; }
.codehilite .nb, .codehilite .bp { color: #79c0ff; }
"""

HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
{vars}
{base}
{pygments}
</style>
</head>
<body>
<article class="markdown-body">
{content}
</article>
</body>
</html>
"""


# --------------------------------------------------------------------------- #
#  WebEnginePage – externé odkazy otvárame v prehliadači                       #
# --------------------------------------------------------------------------- #

class ReaderPage(QWebEnginePage):
    def acceptNavigationRequest(self, url: QUrl, nav_type, is_main_frame):
        if nav_type == QWebEnginePage.NavigationTypeLinkClicked:
            if url.scheme() in ("http", "https", "mailto"):
                QDesktopServices.openUrl(url)
                return False
        return super().acceptNavigationRequest(url, nav_type, is_main_frame)


# --------------------------------------------------------------------------- #
#  Hlavné okno                                                                 #
# --------------------------------------------------------------------------- #

class MdReader(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings(ORG_NAME, APP_NAME)
        self.dark = self.settings.value("dark", False, type=bool)
        self.current_file = None
        self.current_dir = None

        self.watcher = QFileSystemWatcher(self)
        self.watcher.fileChanged.connect(self._on_file_changed)

        self._build_ui()
        self._restore_geometry()

    # ---- UI ---------------------------------------------------------------- #
    def _build_ui(self):
        self.setWindowTitle(APP_NAME)
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mdreader.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.sidebar = QListWidget()
        self.sidebar.setMaximumWidth(280)
        self.sidebar.setMinimumWidth(160)
        self.sidebar.itemClicked.connect(self._on_sidebar_click)

        self.view = QWebEngineView()
        self.view.setPage(ReaderPage(self.view))

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(self.sidebar)
        self.splitter.addWidget(self.view)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([220, 900])

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.splitter)
        self.setCentralWidget(container)

        self._build_toolbar()
        self._render_welcome()

    def _build_toolbar(self):
        tb = self.addToolBar("Hlavné")
        tb.setMovable(False)

        open_file = QAction("Otvoriť súbor", self)
        open_file.setShortcut(QKeySequence.Open)
        open_file.triggered.connect(self.open_file_dialog)
        tb.addAction(open_file)

        open_dir = QAction("Otvoriť priečinok", self)
        open_dir.setShortcut("Ctrl+Shift+O")
        open_dir.triggered.connect(self.open_dir_dialog)
        tb.addAction(open_dir)

        tb.addSeparator()

        self.theme_action = QAction("Tmavý režim", self)
        self.theme_action.setCheckable(True)
        self.theme_action.setChecked(self.dark)
        self.theme_action.setShortcut("Ctrl+D")
        self.theme_action.triggered.connect(self.toggle_theme)
        tb.addAction(self.theme_action)

        toggle_sidebar = QAction("Panel", self)
        toggle_sidebar.setShortcut("Ctrl+B")
        toggle_sidebar.triggered.connect(self._toggle_sidebar)
        tb.addAction(toggle_sidebar)

    # ---- otváranie --------------------------------------------------------- #
    def open_file_dialog(self):
        start = self.current_dir or os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(
            self, "Otvoriť Markdown", start,
            "Markdown (*.md *.markdown *.mdown *.mkd *.txt);;Všetky súbory (*.*)",
        )
        if path:
            self.load_file(path)

    def open_dir_dialog(self):
        start = self.current_dir or os.path.expanduser("~")
        path = QFileDialog.getExistingDirectory(self, "Otvoriť priečinok", start)
        if path:
            self.populate_sidebar(path)

    def load_file(self, path):
        path = os.path.abspath(path)
        if not os.path.isfile(path):
            return

        # sledovanie zmien súboru
        if self.current_file and self.current_file in self.watcher.files():
            self.watcher.removePath(self.current_file)
        self.watcher.addPath(path)

        self.current_file = path
        new_dir = os.path.dirname(path)
        if new_dir != self.current_dir:
            self.populate_sidebar(new_dir, select=path)
        else:
            self._highlight_sidebar(path)

        self._render_file(path)
        self.setWindowTitle(f"{os.path.basename(path)} — {APP_NAME}")

    def _render_file(self, path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                text = fh.read()
        except (OSError, UnicodeDecodeError) as exc:
            self._render_html(f"<h1>Chyba pri čítaní súboru</h1><pre>{exc}</pre>")
            return

        html = markdown.markdown(
            text,
            extensions=[
                "extra",          # tabuľky, fenced code, footnotes, atď.
                "codehilite",     # zvýraznenie syntaxe (Pygments)
                "sane_lists",
                "toc",
                "admonition",
                "nl2br",
            ],
            extension_configs={
                "codehilite": {"guess_lang": False, "css_class": "codehilite"},
            },
        )
        self._render_html(html, base_dir=os.path.dirname(path))

    def _render_html(self, content, base_dir=None):
        page = HTML_TEMPLATE.format(
            vars=DARK_VARS if self.dark else LIGHT_VARS,
            base=BASE_CSS,
            pygments=PYGMENTS_DARK if self.dark else PYGMENTS_LIGHT,
            content=content,
        )
        base_url = QUrl.fromLocalFile(base_dir + os.sep) if base_dir else QUrl()
        self.view.setHtml(page, base_url)

    def _render_welcome(self):
        self._render_html(
            "<h1>MD Reader</h1>"
            "<p>Otvor Markdown súbor cez <b>Otvoriť súbor</b> (Ctrl+O), "
            "alebo priečinok cez <b>Otvoriť priečinok</b> (Ctrl+Shift+O).</p>"
            "<p>Súbory <code>.md</code> môžeš otvárať aj dvojklikom z Prieskumníka.</p>"
        )

    # ---- bočný panel ------------------------------------------------------- #
    def populate_sidebar(self, directory, select=None):
        self.current_dir = directory
        self.sidebar.clear()
        try:
            entries = sorted(
                (f for f in os.listdir(directory)
                 if f.lower().endswith((".md", ".markdown", ".mdown", ".mkd"))),
                key=str.lower,
            )
        except OSError:
            entries = []
        for name in entries:
            item = QListWidgetItem(name)
            item.setData(Qt.UserRole, os.path.join(directory, name))
            self.sidebar.addItem(item)
        if select:
            self._highlight_sidebar(select)

    def _highlight_sidebar(self, path):
        for i in range(self.sidebar.count()):
            item = self.sidebar.item(i)
            if item.data(Qt.UserRole) == path:
                self.sidebar.setCurrentItem(item)
                break

    def _on_sidebar_click(self, item):
        self.load_file(item.data(Qt.UserRole))

    def _toggle_sidebar(self):
        self.sidebar.setVisible(not self.sidebar.isVisible())

    # ---- téma -------------------------------------------------------------- #
    def toggle_theme(self):
        self.dark = self.theme_action.isChecked()
        self.settings.setValue("dark", self.dark)
        if self.current_file:
            self._render_file(self.current_file)
        else:
            self._render_welcome()

    # ---- auto-reload ------------------------------------------------------- #
    def _on_file_changed(self, path):
        # niektoré editory súbor prepíšu (zmiznutie a znovuvytvorenie) –
        # počkáme chvíľu a znova pridáme cestu do watcheru
        def reload():
            if os.path.isfile(path):
                if path not in self.watcher.files():
                    self.watcher.addPath(path)
                if path == self.current_file:
                    self._render_file(path)
        QTimer.singleShot(120, reload)

    # ---- geometria okna ---------------------------------------------------- #
    def _restore_geometry(self):
        geo = self.settings.value("geometry")
        if geo is not None:
            self.restoreGeometry(geo)
        else:
            self.resize(1150, 800)

    def closeEvent(self, event):
        self.settings.setValue("geometry", self.saveGeometry())
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)

    win = MdReader()
    win.show()

    # súbor z argumentu (asociácia .md / "Otvoriť pomocou")
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if args and os.path.isfile(args[0]):
        win.load_file(args[0])

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
