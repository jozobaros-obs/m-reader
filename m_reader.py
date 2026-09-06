#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
M Reader - čítačka a konvertor dokumentov pre Windows.

Zobrazuje Markdown (.md), HTML (.html/.htm) a PDF (.pdf) súbory a umožňuje
ich vzájomný export do Markdownu, PDF alebo HTML. Ďalej ponúka:
  * Renderovanie Markdownu v štýle GitHubu + zvýrazňovanie kódu (Pygments).
  * Prepínateľný bočný panel: súbory v priečinku / obsah dokumentu (TOC).
  * Vyhľadávanie v texte (Ctrl+F).
  * Svetlú / tmavú tému a viacjazyčné UI (EN, SK, RU, ES).
  * Otvorenie súboru cez argument príkazového riadka (asociácia .md/.html/.pdf).
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata

import markdown
from PySide6.QtCore import Qt, QFileSystemWatcher, QLocale, QSettings, QUrl, QTimer
from PySide6.QtGui import QAction, QDesktopServices, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
    QVBoxLayout,
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings

# voliteľné závislosti pre konverziu PDF <-> ostatné formáty
try:
    import pymupdf as fitz  # PyMuPDF (nový názov balíka)
except ImportError:
    try:
        import fitz  # staršie PyMuPDF
    except ImportError:
        fitz = None
try:
    from markdownify import markdownify as html_to_markdown
except ImportError:
    html_to_markdown = None
# text-to-speech (offline, vstavané SAPI hlasy Windows) – voliteľné
try:
    from PySide6.QtTextToSpeech import QTextToSpeech
except ImportError:
    QTextToSpeech = None
# detekcia jazyka textu (offline) pre výber správneho hlasu – voliteľné
try:
    from langdetect import detect as detect_language
except ImportError:
    detect_language = None

APP_NAME = "M Reader"
ORG_NAME = "MReader"

MD_EXTS = (".md", ".markdown", ".mdown", ".mkd", ".txt")
HTML_EXTS = (".html", ".htm")
PDF_EXTS = (".pdf",)
ALL_EXTS = MD_EXTS + HTML_EXTS + PDF_EXTS


def resource_path(name):
    """Cesta k priloženému súboru – funguje pri spustení zo skriptu aj
    z .exe zabaleného PyInstallerom (sys._MEIPASS)."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def file_kind(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in HTML_EXTS:
        return "html"
    if ext in PDF_EXTS:
        return "pdf"
    return "md"


def find_espeak():
    """Nájde espeak-ng.exe (offline TTS, podporuje aj jazyky, ktoré Windows
    hlasy nemajú – napr. slovenčinu). Vráti cestu alebo None."""
    for p in (r"C:\Program Files\eSpeak NG\espeak-ng.exe",
              r"C:\Program Files (x86)\eSpeak NG\espeak-ng.exe"):
        if os.path.isfile(p):
            return p
    return shutil.which("espeak-ng")


def github_slugify(value, separator="-"):
    """Vytvorí ID nadpisu rovnako ako GitHub, aby odkazy v obsahu (TOC)
    fungovali. Na rozdiel od predvoleného slugify v python-markdown
    NESTLÁČA viacnásobné medzery do jednej pomlčky
    (napr. ``try / except`` -> ``try--except``)."""
    value = unicodedata.normalize("NFC", value).strip().lower()
    value = re.sub(r"[^\w\s-]", "", value, flags=re.UNICODE)   # zahoď interpunkciu
    value = re.sub(r"\s", separator, value)                     # každá medzera -> pomlčka
    return value


# --------------------------------------------------------------------------- #
#  Lokalizácia UI                                                              #
# --------------------------------------------------------------------------- #

DEFAULT_LANG = "en"

LANGUAGES = [
    ("en", "English"),
    ("sk", "Slovenčina"),
    ("ru", "Русский"),
    ("es", "Español"),
]

TRANSLATIONS = {
    "en": {
        "open_file": "Open file",
        "open_folder": "Open folder",
        "dark_mode": "Dark mode",
        "panel": "Panel",
        "find": "Find",
        "find_ph": "Find in text…",
        "export": "Export",
        "export_md": "To Markdown",
        "export_pdf": "To PDF",
        "export_html": "To HTML",
        "read_aloud": "Read aloud",
        "stop_reading": "Stop reading",
        "files": "Files",
        "outline": "Contents",
        "language_tip": "Language",
        "dlg_open": "Open document",
        "dlg_open_folder": "Open folder",
        "dlg_export": "Export as",
        "filter_all": "Documents (*.md *.markdown *.html *.htm *.pdf);;All files (*.*)",
        "read_error": "Error reading file",
        "saved": "Saved:",
        "export_fail": "Export failed",
        "need_pymupdf": "PDF conversion needs PyMuPDF (pip install PyMuPDF).",
        "need_markdownify": "HTML→Markdown needs markdownify (pip install markdownify).",
        "welcome": (
            "<h1>M Reader</h1>"
            "<p>Open a <b>Markdown</b>, <b>HTML</b> or <b>PDF</b> file via "
            "<b>Open file</b> (Ctrl+O), or a folder via <b>Open folder</b> "
            "(Ctrl+Shift+O).</p>"
            "<p>Use <b>Export</b> to convert between Markdown, PDF and HTML, "
            "and <b>Ctrl+F</b> to search in the text.</p>"
        ),
    },
    "sk": {
        "open_file": "Otvoriť súbor",
        "open_folder": "Otvoriť priečinok",
        "dark_mode": "Tmavý režim",
        "panel": "Panel",
        "find": "Hľadať",
        "find_ph": "Hľadať v texte…",
        "export": "Export",
        "export_md": "Do Markdownu",
        "export_pdf": "Do PDF",
        "export_html": "Do HTML",
        "read_aloud": "Prečítať nahlas",
        "stop_reading": "Zastaviť čítanie",
        "files": "Súbory",
        "outline": "Obsah",
        "language_tip": "Jazyk",
        "dlg_open": "Otvoriť dokument",
        "dlg_open_folder": "Otvoriť priečinok",
        "dlg_export": "Exportovať ako",
        "filter_all": "Dokumenty (*.md *.markdown *.html *.htm *.pdf);;Všetky súbory (*.*)",
        "read_error": "Chyba pri čítaní súboru",
        "saved": "Uložené:",
        "export_fail": "Export zlyhal",
        "need_pymupdf": "Konverzia PDF vyžaduje PyMuPDF (pip install PyMuPDF).",
        "need_markdownify": "HTML→Markdown vyžaduje markdownify (pip install markdownify).",
        "welcome": (
            "<h1>M Reader</h1>"
            "<p>Otvor súbor <b>Markdown</b>, <b>HTML</b> alebo <b>PDF</b> cez "
            "<b>Otvoriť súbor</b> (Ctrl+O), alebo priečinok cez "
            "<b>Otvoriť priečinok</b> (Ctrl+Shift+O).</p>"
            "<p><b>Export</b> prevedie dokument medzi Markdownom, PDF a HTML, "
            "<b>Ctrl+F</b> hľadá v texte.</p>"
        ),
    },
    "ru": {
        "open_file": "Открыть файл",
        "open_folder": "Открыть папку",
        "dark_mode": "Тёмный режим",
        "panel": "Панель",
        "find": "Поиск",
        "find_ph": "Поиск в тексте…",
        "export": "Экспорт",
        "export_md": "В Markdown",
        "export_pdf": "В PDF",
        "export_html": "В HTML",
        "read_aloud": "Озвучить",
        "stop_reading": "Остановить",
        "files": "Файлы",
        "outline": "Содержание",
        "language_tip": "Язык",
        "dlg_open": "Открыть документ",
        "dlg_open_folder": "Открыть папку",
        "dlg_export": "Экспортировать как",
        "filter_all": "Документы (*.md *.markdown *.html *.htm *.pdf);;Все файлы (*.*)",
        "read_error": "Ошибка чтения файла",
        "saved": "Сохранено:",
        "export_fail": "Ошибка экспорта",
        "need_pymupdf": "Для конвертации PDF нужен PyMuPDF (pip install PyMuPDF).",
        "need_markdownify": "Для HTML→Markdown нужен markdownify (pip install markdownify).",
        "welcome": (
            "<h1>M Reader</h1>"
            "<p>Откройте файл <b>Markdown</b>, <b>HTML</b> или <b>PDF</b> через "
            "<b>Открыть файл</b> (Ctrl+O), или папку через <b>Открыть папку</b> "
            "(Ctrl+Shift+O).</p>"
            "<p><b>Экспорт</b> конвертирует документ между Markdown, PDF и HTML, "
            "<b>Ctrl+F</b> ищет в тексте.</p>"
        ),
    },
    "es": {
        "open_file": "Abrir archivo",
        "open_folder": "Abrir carpeta",
        "dark_mode": "Modo oscuro",
        "panel": "Panel",
        "find": "Buscar",
        "find_ph": "Buscar en el texto…",
        "export": "Exportar",
        "export_md": "A Markdown",
        "export_pdf": "A PDF",
        "export_html": "A HTML",
        "read_aloud": "Leer en voz alta",
        "stop_reading": "Detener lectura",
        "files": "Archivos",
        "outline": "Contenido",
        "language_tip": "Idioma",
        "dlg_open": "Abrir documento",
        "dlg_open_folder": "Abrir carpeta",
        "dlg_export": "Exportar como",
        "filter_all": "Documentos (*.md *.markdown *.html *.htm *.pdf);;Todos los archivos (*.*)",
        "read_error": "Error al leer el archivo",
        "saved": "Guardado:",
        "export_fail": "Error de exportación",
        "need_pymupdf": "La conversión de PDF necesita PyMuPDF (pip install PyMuPDF).",
        "need_markdownify": "HTML→Markdown necesita markdownify (pip install markdownify).",
        "welcome": (
            "<h1>M Reader</h1>"
            "<p>Abre un archivo <b>Markdown</b>, <b>HTML</b> o <b>PDF</b> con "
            "<b>Abrir archivo</b> (Ctrl+O), o una carpeta con <b>Abrir carpeta</b> "
            "(Ctrl+Shift+O).</p>"
            "<p>Usa <b>Exportar</b> para convertir entre Markdown, PDF y HTML, "
            "y <b>Ctrl+F</b> para buscar en el texto.</p>"
        ),
    },
}


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
<script>{script}</script>
</body>
</html>
"""

# Robustné spracovanie klikov na kotvy v obsahu (TOC). Funguje pre súbory
# generované AKÝMKOĽVEK nástrojom: ak kotva nesedí presne, nájde nadpis
# "fuzzy" porovnaním (ignoruje počet pomlčiek aj interpunkciu).
ANCHOR_JS = r"""
(function () {
    function norm(s) {
        try { s = decodeURIComponent(s); } catch (e) {}
        return (s || "").toLowerCase().replace(/[^a-z0-9]+/g, "");
    }
    function findTarget(frag) {
        if (!frag) return null;
        var el = document.getElementById(frag);
        if (el) return el;
        try {
            el = document.querySelector('[name="' + CSS.escape(frag) + '"]');
            if (el) return el;
        } catch (e) {}
        var nf = norm(frag);
        if (!nf) return null;
        var heads = document.querySelectorAll("h1,h2,h3,h4,h5,h6");
        for (var i = 0; i < heads.length; i++) {
            if (heads[i].id && norm(heads[i].id) === nf) return heads[i];
        }
        for (var i = 0; i < heads.length; i++) {
            if (norm(heads[i].textContent) === nf) return heads[i];
        }
        return null;
    }
    document.addEventListener("click", function (e) {
        var a = e.target && e.target.closest ? e.target.closest("a") : null;
        if (!a) return;
        var href = a.getAttribute("href") || "";
        if (href.charAt(0) !== "#") return;
        var t = findTarget(href.slice(1));
        if (t) {
            e.preventDefault();
            t.scrollIntoView({ behavior: "smooth", block: "start" });
        }
    }, true);
})();
"""

# Priradí ID nadpisom v ľubovoľnom HTML a vráti zoznam pre bočný obsah.
OUTLINE_JS = r"""
(function () {
    var hs = document.querySelectorAll("h1,h2,h3,h4,h5,h6");
    var out = [];
    for (var i = 0; i < hs.length; i++) {
        var h = hs[i];
        var text = (h.textContent || "").trim();
        if (!text) continue;
        if (!h.id) { h.id = "mr-h-" + i; }
        out.push({ level: parseInt(h.tagName.substring(1), 10), text: text, id: h.id });
    }
    return JSON.stringify(out);
})();
"""

# Sleduje kam používateľ klikol v texte (kurzor) – uloží pozíciu, aby sa
# dala použiť ako začiatok čítania. Injektuje sa po načítaní stránky.
CARET_TRACK_JS = r"""
(function () {
    if (window.__mrTracker) return;
    window.__mrTracker = true;
    window.__mrStart = null;
    document.addEventListener("click", function (e) {
        var pos = null;
        if (document.caretRangeFromPoint) {
            var r = document.caretRangeFromPoint(e.clientX, e.clientY);
            if (r) pos = { c: r.startContainer, o: r.startOffset };
        } else if (document.caretPositionFromPoint) {
            var p = document.caretPositionFromPoint(e.clientX, e.clientY);
            if (p) pos = { c: p.offsetNode, o: p.offset };
        }
        window.__mrStart = pos;
    }, true);
})();
"""

# Text pre nahlas čítanie: 1) označený text, 2) od miesta posledného kliknutia
# (kurzora) po koniec, 3) od prvého viditeľného odseku po koniec.
SPEAK_JS = r"""
(function () {
    var sel = window.getSelection ? window.getSelection().toString() : "";
    if (sel && sel.trim()) return sel;
    try {
        if (window.__mrStart && window.__mrStart.c && document.body) {
            var startNode = window.__mrStart.c;
            var walker = document.createTreeWalker(
                document.body, NodeFilter.SHOW_TEXT, {
                    acceptNode: function (n) {
                        var p = n.parentNode;
                        while (p) {
                            if (p.tagName === "SCRIPT" || p.tagName === "STYLE")
                                return NodeFilter.FILTER_REJECT;
                            p = p.parentNode;
                        }
                        return NodeFilter.FILTER_ACCEPT;
                    }
                });
            var parts = [], started = false, node;
            while ((node = walker.nextNode())) {
                if (!started) {
                    if (node === startNode) {
                        started = true;
                        parts.push(node.data.substring(window.__mrStart.o));
                    }
                    continue;
                }
                parts.push(node.data);
            }
            var t = parts.join("");
            if (t && t.trim()) return t;
        }
    } catch (e) {}
    var blocks = document.querySelectorAll(
        "p,li,h1,h2,h3,h4,h5,h6,pre,td,th,blockquote");
    var out = [];
    var started = false;
    for (var i = 0; i < blocks.length; i++) {
        if (!started) {
            var r = blocks[i].getBoundingClientRect();
            if (r.bottom > 4) started = true;   // prvý blok vo viewporte
        }
        if (started) {
            var tx = (blocks[i].innerText || blocks[i].textContent || "").trim();
            if (tx) out.push(tx);
        }
    }
    if (!out.length && document.body) return document.body.innerText || "";
    return out.join("\n");
})();
"""


# --------------------------------------------------------------------------- #
#  WebEnginePage – externé odkazy otvárame v prehliadači                       #
# --------------------------------------------------------------------------- #

class ReaderPage(QWebEnginePage):
    def acceptNavigationRequest(self, url, nav_type, is_main_frame):
        if nav_type == QWebEnginePage.NavigationType.NavigationTypeLinkClicked:
            if url.scheme() in ("http", "https", "mailto"):
                QDesktopServices.openUrl(url)
                return False
        return super().acceptNavigationRequest(url, nav_type, is_main_frame)


# --------------------------------------------------------------------------- #
#  Hlavné okno                                                                 #
# --------------------------------------------------------------------------- #

class MReader(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings(ORG_NAME, APP_NAME)
        self.dark = self.settings.value("dark", False, type=bool)
        self.lang = self.settings.value("lang", DEFAULT_LANG)
        if self.lang not in TRANSLATIONS:
            self.lang = DEFAULT_LANG
        self.current_file = None
        self.current_dir = None
        self.current_kind = None
        self.current_body_html = ""   # renderované telo (pre export MD -> HTML)
        self._pending_scroll = None   # pozícia rolovania na obnovenie po prekreslení

        self.watcher = QFileSystemWatcher(self)
        self.watcher.fileChanged.connect(self._on_file_changed)

        # text-to-speech engine (offline). Uprednostní 'winrt' (OneCore hlasy
        # Windows – podporujú viac jazykov a dajú sa dosťahovať).
        self.tts = None
        if QTextToSpeech:
            engines = QTextToSpeech.availableEngines()
            preferred = [e for e in ("winrt", "sapi") if e in engines]
            eng = preferred[0] if preferred else (engines[0] if engines else "")
            self.tts = QTextToSpeech(eng, self) if eng else QTextToSpeech(self)
        # eSpeak NG – záloha pre jazyky bez Windows hlasu (napr. slovenčina)
        self.espeak_path = find_espeak()
        self._espeak_proc = None
        self._espeak_tmp = None

        self._build_ui()
        self._restore_geometry()

    # ---- UI ---------------------------------------------------------------- #
    def _build_ui(self):
        self.setWindowTitle(APP_NAME)
        icon_path = resource_path("mdreader.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.sidebar = QListWidget()
        self.sidebar.itemClicked.connect(self._on_sidebar_click)

        self.outline = QTreeWidget()
        self.outline.setHeaderHidden(True)
        self.outline.itemClicked.connect(self._on_outline_click)

        self.panel = QTabWidget()
        self.panel.setMaximumWidth(320)
        self.panel.setMinimumWidth(160)
        self.panel.addTab(self.sidebar, self.t("files"))
        self.panel.addTab(self.outline, self.t("outline"))

        self.view = QWebEngineView()
        self.view.setPage(ReaderPage(self.view))
        s = self.view.settings()
        s.setAttribute(QWebEngineSettings.WebAttribute.PdfViewerEnabled, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.PluginsEnabled, True)
        self.view.page().pdfPrintingFinished.connect(self._on_pdf_printed)
        self.view.loadFinished.connect(self._on_load_finished)

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(self.panel)
        self.splitter.addWidget(self.view)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([240, 900])

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._build_find_bar())
        layout.addWidget(self.splitter)
        self.setCentralWidget(container)

        self._build_toolbar()
        self._render_welcome()

    def _build_find_bar(self):
        self.find_bar = QWidget()
        h = QHBoxLayout(self.find_bar)
        h.setContentsMargins(8, 4, 8, 4)
        self.find_input = QLineEdit()
        self.find_input.returnPressed.connect(lambda: self._find(False))
        self.find_input.textChanged.connect(lambda _t: self._find(False))
        self.find_prev = QPushButton("▲")
        self.find_prev.setFixedWidth(32)
        self.find_prev.clicked.connect(lambda: self._find(True))
        self.find_next = QPushButton("▼")
        self.find_next.setFixedWidth(32)
        self.find_next.clicked.connect(lambda: self._find(False))
        self.find_close = QPushButton("✕")
        self.find_close.setFixedWidth(32)
        self.find_close.clicked.connect(self._hide_find)
        h.addWidget(self.find_input)
        h.addWidget(self.find_prev)
        h.addWidget(self.find_next)
        h.addWidget(self.find_close)
        self.find_bar.hide()
        return self.find_bar

    def _build_toolbar(self):
        tb = self.addToolBar("Main")
        tb.setMovable(False)

        self.open_file_action = QAction(self)
        self.open_file_action.setShortcut(QKeySequence.Open)
        self.open_file_action.triggered.connect(self.open_file_dialog)
        tb.addAction(self.open_file_action)

        self.open_dir_action = QAction(self)
        self.open_dir_action.setShortcut("Ctrl+Shift+O")
        self.open_dir_action.triggered.connect(self.open_dir_dialog)
        tb.addAction(self.open_dir_action)

        tb.addSeparator()

        # Export s rozbaľovacím menu
        self.export_button = QToolButton()
        self.export_button.setPopupMode(QToolButton.InstantPopup)
        self.export_menu = QMenu(self.export_button)
        self.export_md_action = self.export_menu.addAction("", lambda: self.export("md"))
        self.export_pdf_action = self.export_menu.addAction("", lambda: self.export("pdf"))
        self.export_html_action = self.export_menu.addAction("", lambda: self.export("html"))
        self.export_button.setMenu(self.export_menu)
        tb.addWidget(self.export_button)

        self.find_action = QAction(self)
        self.find_action.setShortcut(QKeySequence.Find)
        self.find_action.triggered.connect(self._show_find)
        tb.addAction(self.find_action)

        # Prečítať nahlas (ak je dostupné Windows TTS alebo eSpeak NG)
        if self.tts or self.espeak_path:
            self.speak_action = QAction(self)
            self.speak_action.setShortcut("Ctrl+R")
            self.speak_action.triggered.connect(self.speak_selection)
            tb.addAction(self.speak_action)

            self.stop_action = QAction(self)
            self.stop_action.triggered.connect(self.stop_speaking)
            tb.addAction(self.stop_action)

        tb.addSeparator()

        self.theme_action = QAction(self)
        self.theme_action.setCheckable(True)
        self.theme_action.setChecked(self.dark)
        self.theme_action.setShortcut("Ctrl+D")
        self.theme_action.triggered.connect(self.toggle_theme)
        tb.addAction(self.theme_action)

        self.panel_action = QAction(self)
        self.panel_action.setShortcut("Ctrl+B")
        self.panel_action.triggered.connect(self._toggle_sidebar)
        tb.addAction(self.panel_action)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)

        self.lang_combo = QComboBox()
        for code, name in LANGUAGES:
            self.lang_combo.addItem(name, code)
        idx = self.lang_combo.findData(self.lang)
        if idx >= 0:
            self.lang_combo.setCurrentIndex(idx)
        self.lang_combo.currentIndexChanged.connect(self._on_language_change)
        tb.addWidget(self.lang_combo)

        self._retranslate()

    # ---- lokalizácia ------------------------------------------------------- #
    def t(self, key):
        lang = TRANSLATIONS.get(self.lang, TRANSLATIONS[DEFAULT_LANG])
        return lang.get(key, TRANSLATIONS[DEFAULT_LANG].get(key, key))

    def _retranslate(self):
        self.open_file_action.setText(self.t("open_file"))
        self.open_dir_action.setText(self.t("open_folder"))
        self.export_button.setText(self.t("export"))
        self.export_md_action.setText(self.t("export_md"))
        self.export_pdf_action.setText(self.t("export_pdf"))
        self.export_html_action.setText(self.t("export_html"))
        self.find_action.setText(self.t("find"))
        if self.tts or self.espeak_path:
            self.speak_action.setText(self.t("read_aloud"))
            self.stop_action.setText(self.t("stop_reading"))
        self.theme_action.setText(self.t("dark_mode"))
        self.panel_action.setText(self.t("panel"))
        self.find_input.setPlaceholderText(self.t("find_ph"))
        self.lang_combo.setToolTip(self.t("language_tip"))
        self.panel.setTabText(0, self.t("files"))
        self.panel.setTabText(1, self.t("outline"))
        if not self.current_file:
            self._render_welcome()

    def _on_language_change(self, _index):
        code = self.lang_combo.currentData()
        if code and code != self.lang:
            self.lang = code
            self.settings.setValue("lang", code)
            self._retranslate()

    # ---- otváranie --------------------------------------------------------- #
    def open_file_dialog(self):
        start = self.current_dir or os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(
            self, self.t("dlg_open"), start, self.t("filter_all"),
        )
        if path:
            self.load_file(path)

    def open_dir_dialog(self):
        start = self.current_dir or os.path.expanduser("~")
        path = QFileDialog.getExistingDirectory(self, self.t("dlg_open_folder"), start)
        if path:
            self.populate_sidebar(path)

    def load_file(self, path):
        path = os.path.abspath(path)
        if not os.path.isfile(path):
            return

        if self.current_file and self.current_file in self.watcher.files():
            self.watcher.removePath(self.current_file)
        self.watcher.addPath(path)

        self.current_file = path
        self.current_kind = file_kind(path)
        new_dir = os.path.dirname(path)
        if new_dir != self.current_dir:
            self.populate_sidebar(new_dir, select=path)
        else:
            self._highlight_sidebar(path)

        self.outline.clear()
        if self.current_kind == "md":
            self._render_markdown(path)
        elif self.current_kind == "html":
            self.view.setUrl(QUrl.fromLocalFile(path))
        elif self.current_kind == "pdf":
            # PDF prehliadač má vlastný (funkčný) obsah – náš zbytočný TOC
            # nezobrazujeme, prepneme na záložku Súbory.
            self.panel.setCurrentIndex(0)
            self.view.setUrl(QUrl.fromLocalFile(path))

        self.setWindowTitle(f"{os.path.basename(path)} — {APP_NAME}")

    # ---- renderovanie ------------------------------------------------------ #
    def _render_markdown(self, path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                text = fh.read()
        except (OSError, UnicodeDecodeError) as exc:
            self._render_html(f"<h1>{self.t('read_error')}</h1><pre>{exc}</pre>")
            return

        md = markdown.Markdown(
            extensions=["extra", "codehilite", "sane_lists", "toc",
                        "admonition", "nl2br"],
            extension_configs={
                "codehilite": {"guess_lang": False, "css_class": "codehilite"},
                "toc": {"slugify": github_slugify},
            },
        )
        body = md.convert(text)
        self.current_body_html = body
        self._populate_outline(getattr(md, "toc_tokens", []))
        self._render_html(body, base_dir=os.path.dirname(path))

    def _build_page(self, content):
        return HTML_TEMPLATE.format(
            vars=DARK_VARS if self.dark else LIGHT_VARS,
            base=BASE_CSS,
            pygments=PYGMENTS_DARK if self.dark else PYGMENTS_LIGHT,
            content=content,
            script=ANCHOR_JS,
        )

    def _render_html(self, content, base_dir=None):
        page = self._build_page(content)
        base_url = QUrl.fromLocalFile(base_dir + os.sep) if base_dir else QUrl()
        self.view.setHtml(page, base_url)

    def _render_welcome(self):
        self.current_body_html = self.t("welcome")
        self._render_html(self.t("welcome"))

    # ---- bočný panel: súbory ----------------------------------------------- #
    def populate_sidebar(self, directory, select=None):
        self.current_dir = directory
        self.sidebar.clear()
        try:
            entries = sorted(
                (f for f in os.listdir(directory) if f.lower().endswith(ALL_EXTS)),
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
        self.panel.setVisible(not self.panel.isVisible())

    # ---- bočný panel: obsah dokumentu -------------------------------------- #
    def _populate_outline(self, tokens):
        """Obsah z toc_tokens (Markdown) – vnorená štruktúra."""
        self.outline.clear()

        def add(parent, node):
            item = QTreeWidgetItem([node.get("name", "")])
            item.setData(0, Qt.UserRole, ("anchor", node.get("id", "")))
            (self.outline.addTopLevelItem if parent is None else parent.addChild)(item)
            for child in node.get("children", []):
                add(item, child)

        for tok in tokens:
            add(None, tok)
        self.outline.expandAll()

    def _populate_outline_flat(self, headings):
        """Obsah z plochého zoznamu {level,text,id} (HTML) -> vnorí podľa úrovní."""
        self.outline.clear()
        stack = []  # (level, item)
        for h in headings:
            level, text, hid = h["level"], h["text"], h["id"]
            item = QTreeWidgetItem([text])
            item.setData(0, Qt.UserRole, ("anchor", hid))
            while stack and stack[-1][0] >= level:
                stack.pop()
            if stack:
                stack[-1][1].addChild(item)
            else:
                self.outline.addTopLevelItem(item)
            stack.append((level, item))
        self.outline.expandAll()

    def _on_outline_click(self, item, _column=0):
        data = item.data(0, Qt.UserRole)
        if not data:
            return
        kind, value = data
        if kind == "anchor" and value:
            self._scroll_to(value)

    def _scroll_to(self, anchor):
        js = (
            "var e=document.getElementById(%s);"
            "if(e){e.scrollIntoView({behavior:'smooth',block:'start'});}"
            % json.dumps(anchor)
        )
        self.view.page().runJavaScript(js)

    def _on_load_finished(self, ok):
        if not ok:
            return
        # sleduj kliknutia (kurzor) pre čítanie od pozície – md aj html
        if self.current_kind in ("md", "html"):
            self.view.page().runJavaScript(CARET_TRACK_JS)
        # pre HTML súbory zostavíme obsah až po načítaní stránky
        if self.current_kind == "html":
            self.view.page().runJavaScript(OUTLINE_JS, self._apply_html_outline)
        # obnov pozíciu rolovania po prekreslení (napr. po zmene témy)
        if self._pending_scroll:
            y = self._pending_scroll
            self._pending_scroll = None
            self.view.page().runJavaScript(f"window.scrollTo(0, {y});")

    def _apply_html_outline(self, result):
        try:
            headings = json.loads(result) if result else []
        except (ValueError, TypeError):
            headings = []
        if headings:
            self._populate_outline_flat(headings)

    # ---- vyhľadávanie ------------------------------------------------------ #
    def _show_find(self):
        self.find_bar.show()
        self.find_input.setFocus()
        self.find_input.selectAll()

    def _hide_find(self):
        self.find_bar.hide()
        self.view.page().findText("")   # zruší zvýraznenie
        self.view.setFocus()

    def _find(self, backward):
        text = self.find_input.text()
        flags = QWebEnginePage.FindFlag.FindBackward if backward else QWebEnginePage.FindFlag(0)
        self.view.page().findText(text, flags)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape and self.find_bar.isVisible():
            self._hide_find()
            return
        super().keyPressEvent(event)

    # ---- čítanie nahlas (TTS) ---------------------------------------------- #
    def speak_selection(self):
        """Prečíta označený text; ak nič nie je označené, číta od miesta
        posledného kliknutia (kurzora), inak od prvého viditeľného odseku."""
        if not (self.tts or self.espeak_path):
            return
        self.view.page().runJavaScript(SPEAK_JS, self._speak_text)

    def _speak_text(self, text):
        if not text or not text.strip():
            return
        self.stop_speaking()
        code = self._detect_lang(text)
        # 1) prirodzený Windows hlas pre daný jazyk (ak existuje)
        if self.tts and self._set_windows_voice(code):
            self.tts.say(text)
            return
        # 2) eSpeak NG – offline, podporuje aj jazyky bez Windows hlasu (sk…)
        if self.espeak_path and code and self._speak_espeak(text, code):
            return
        # 3) posledná záchrana – predvolený Windows hlas
        if self.tts:
            self.tts.say(text)

    def _detect_lang(self, text):
        if not detect_language:
            return None
        try:
            return detect_language(text.strip()[:1000])   # 'en','sk','ru','es'…
        except Exception:
            return None

    def _set_windows_voice(self, code):
        """Nastaví Windows hlas pre jazyk (aj naprieč enginmi). True ak sa
        podarilo nájsť zodpovedajúci hlas."""
        if not (self.tts and code):
            return False
        target = QLocale(code).language()
        for loc in self.tts.availableLocales():
            if loc.language() == target:
                self.tts.setLocale(loc)
                return True
        current = self.tts.engine()
        for eng in QTextToSpeech.availableEngines():
            if eng in ("mock", current):
                continue
            try:
                probe = QTextToSpeech(eng)
            except Exception:
                continue
            for loc in probe.availableLocales():
                if loc.language() == target:
                    self.tts.setEngine(eng)
                    self.tts.setLocale(loc)
                    return True
        return False

    def _speak_espeak(self, text, code):
        """Prehrá text cez eSpeak NG (asynchrónne, bez okna konzoly)."""
        try:
            fd, path = tempfile.mkstemp(suffix=".txt", prefix="mreader_")
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(text)
            flags = 0x08000000 if sys.platform == "win32" else 0  # CREATE_NO_WINDOW
            self._espeak_proc = subprocess.Popen(
                [self.espeak_path, "-v", code, "-f", path],
                creationflags=flags,
            )
            self._espeak_tmp = path
            return True
        except Exception:
            return False

    def stop_speaking(self):
        if self.tts:
            self.tts.stop()
        if self._espeak_proc and self._espeak_proc.poll() is None:
            try:
                self._espeak_proc.terminate()
            except Exception:
                pass
        self._espeak_proc = None
        if self._espeak_tmp and os.path.exists(self._espeak_tmp):
            try:
                os.remove(self._espeak_tmp)
            except OSError:
                pass
            self._espeak_tmp = None

    # ---- export ------------------------------------------------------------ #
    def export(self, target):
        if not self.current_file:
            return
        base = os.path.splitext(os.path.basename(self.current_file))[0]
        ext = {"md": ".md", "pdf": ".pdf", "html": ".html"}[target]
        start = os.path.join(self.current_dir or os.path.expanduser("~"), base + ext)
        dest, _ = QFileDialog.getSaveFileName(self, self.t("dlg_export"), start,
                                              f"*{ext}")
        if not dest:
            return
        try:
            if target == "pdf":
                self._export_pdf(dest)
            elif target == "html":
                self._export_html(dest)
            else:
                self._export_md(dest)
        except Exception as exc:
            QMessageBox.warning(self, self.t("export_fail"), str(exc))

    def _export_pdf(self, dest):
        if self.current_kind == "pdf":
            shutil.copyfile(self.current_file, dest)
            self._notify_saved(dest)
        else:
            # renderovaná stránka -> PDF (asynchrónne, výsledok v _on_pdf_printed)
            self.view.page().printToPdf(dest)

    def _export_html(self, dest):
        if self.current_kind == "html":
            shutil.copyfile(self.current_file, dest)
        elif self.current_kind == "md":
            with open(dest, "w", encoding="utf-8") as fh:
                fh.write(self._build_page(self.current_body_html))
        elif self.current_kind == "pdf":
            if not fitz:
                raise RuntimeError(self.t("need_pymupdf"))
            doc = fitz.open(self.current_file)
            parts = [page.get_text("html") for page in doc]
            doc.close()
            html = ('<!DOCTYPE html><html><head><meta charset="utf-8"></head>'
                    '<body>' + "\n".join(parts) + "</body></html>")
            with open(dest, "w", encoding="utf-8") as fh:
                fh.write(html)
        self._notify_saved(dest)

    def _export_md(self, dest):
        if self.current_kind == "md":
            shutil.copyfile(self.current_file, dest)
        elif self.current_kind == "html":
            if not html_to_markdown:
                raise RuntimeError(self.t("need_markdownify"))
            with open(self.current_file, "r", encoding="utf-8", errors="replace") as fh:
                md_text = html_to_markdown(fh.read())
            with open(dest, "w", encoding="utf-8") as fh:
                fh.write(md_text)
        elif self.current_kind == "pdf":
            if not fitz:
                raise RuntimeError(self.t("need_pymupdf"))
            doc = fitz.open(self.current_file)
            text = "\n\n".join(page.get_text() for page in doc)
            doc.close()
            with open(dest, "w", encoding="utf-8") as fh:
                fh.write(text)
        self._notify_saved(dest)

    def _on_pdf_printed(self, path, success):
        if success:
            self._notify_saved(path)
        else:
            QMessageBox.warning(self, self.t("export_fail"), path)

    def _notify_saved(self, dest):
        self.statusBar().showMessage(f"{self.t('saved')} {dest}", 6000)

    # ---- téma -------------------------------------------------------------- #
    def toggle_theme(self):
        self.dark = self.theme_action.isChecked()
        self.settings.setValue("dark", self.dark)
        if self.current_kind == "md" and self.current_file:
            # najprv zisti aktuálnu pozíciu rolovania, potom prekresli a obnov ju
            self.view.page().runJavaScript("window.scrollY", self._rerender_keep_scroll)
        elif not self.current_file:
            self._render_welcome()

    def _rerender_keep_scroll(self, scroll_y):
        try:
            self._pending_scroll = int(float(scroll_y or 0))
        except (TypeError, ValueError):
            self._pending_scroll = 0
        self._render_markdown(self.current_file)

    # ---- auto-reload ------------------------------------------------------- #
    def _on_file_changed(self, path):
        def reload():
            if os.path.isfile(path):
                if path not in self.watcher.files():
                    self.watcher.addPath(path)
                if path == self.current_file:
                    self.load_file(path)
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
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("MReader.App")
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)

    icon_path = resource_path("mdreader.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    win = MReader()
    win.show()

    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if args and os.path.isfile(args[0]):
        win.load_file(args[0])

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
