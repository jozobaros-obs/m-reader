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
import sys
import threading
import unicodedata

import markdown
from PySide6.QtCore import (
    Qt, QEvent, QFileSystemWatcher, QLocale, QSettings, QUrl, QTimer, Signal,
)
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


def find_tesseract():
    """Nájde tesseract.exe (OCR pre skenované PDF). Vráti cestu alebo None."""
    local = os.environ.get("LOCALAPPDATA", "")
    candidates = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    if local:
        candidates.append(os.path.join(local, "Programs", "Tesseract-OCR",
                                       "tesseract.exe"))
    for p in candidates:
        if os.path.isfile(p):
            return p
    return shutil.which("tesseract")


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
        "zoom_in": "Zoom in",
        "zoom_out": "Zoom out",
        "zoom_reset": "Reset zoom",
        "pdf_no_text": "This PDF has no text layer and OCR is unavailable — nothing to read.",
        "ocr_running": "Reading text from images (OCR)…",
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
        "zoom_in": "Priblížiť",
        "zoom_out": "Oddialiť",
        "zoom_reset": "Pôvodná veľkosť",
        "pdf_no_text": "Toto PDF nemá textovú vrstvu a OCR nie je dostupné — niet čo čítať.",
        "ocr_running": "Načítavam text z obrázkov (OCR)…",
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
        "zoom_in": "Увеличить",
        "zoom_out": "Уменьшить",
        "zoom_reset": "Сбросить масштаб",
        "pdf_no_text": "В этом PDF нет текстового слоя, OCR недоступен — нечего читать.",
        "ocr_running": "Распознаю текст с изображений (OCR)…",
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
        "zoom_in": "Acercar",
        "zoom_out": "Alejar",
        "zoom_reset": "Restablecer zoom",
        "pdf_no_text": "Este PDF no tiene capa de texto y no hay OCR — nada que leer.",
        "ocr_running": "Leyendo texto de las imágenes (OCR)…",
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
    max-width: 1100px;
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
    white-space: pre-wrap;      /* dlhé riadky sa zalomia – žiadny vodorovný posuvník */
    word-break: break-word;
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

/* Export do PDF: využi celú šírku strany a nikdy nezobrazuj posuvníky. */
@media print {
    .markdown-body {
        max-width: none;
        margin: 0;
        padding: 0;
    }
    .markdown-body pre,
    .markdown-body table {
        overflow: visible;
        white-space: pre-wrap;
        word-break: break-word;
    }
    ::-webkit-scrollbar { display: none; }
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
    window.__mrClicks = 0;
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
        // Ohlás kliknutie Pythonu cez zmenu titulku (bez QWebChannel).
        // Ak práve prebieha čítanie, TTS preskočí na toto miesto.
        window.__mrClicks++;
        document.title = "mrjump:" + window.__mrClicks;
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
    _ocr_ready = Signal(str)      # výsledok OCR / textovej vrstvy z vlákna
    _status_signal = Signal(str)  # zobrazenie správy v stavovom riadku z vlákna
    _md_ready = Signal(str, str, object)  # (cesta, telo HTML, toc_tokens)

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
        self.zoom = float(self.settings.value("zoom", 1.0))   # priblíženie textu
        self._reading = False         # práve prebieha čítanie nahlas?
        self._wheel_filter_installed = False

        self.watcher = QFileSystemWatcher(self)
        self.watcher.fileChanged.connect(self._on_file_changed)

        # text-to-speech engine – iba vstavané hlasy Windows (SAPI / OneCore).
        self.tts = None
        if QTextToSpeech:
            engines = QTextToSpeech.availableEngines()
            preferred = [e for e in ("sapi", "winrt") if e in engines]
            eng = preferred[0] if preferred else (engines[0] if engines else "")
            self.tts = QTextToSpeech(eng, self) if eng else QTextToSpeech(self)
            self.tts.stateChanged.connect(self._on_tts_state)
        self.tesseract_path = find_tesseract()   # OCR pre skenované PDF
        self._ocr_ready.connect(self._on_ocr_ready)
        self._status_signal.connect(
            lambda m: self.statusBar().showMessage(m, 0))
        self._md_ready.connect(self._on_md_ready)

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
        # kliknutie v texte sa hlási cez zmenu titulku -> skok čítania TTS
        self.view.titleChanged.connect(self._on_view_title)

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(self.panel)
        self.splitter.addWidget(self.view)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([240, 1120])

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.splitter)
        self.setCentralWidget(container)

        # kompaktný vyhľadávací panel „pláva" nad zobrazením (pravý horný roh)
        self._build_find_bar()
        self.view.installEventFilter(self)   # prepolohuj panel pri zmene veľkosti

        self._build_toolbar()
        self._render_welcome()

    def _build_find_bar(self):
        # plávajúci panel – dieťa zobrazenia, aby sa vykreslil nad dokumentom
        self.find_bar = QWidget(self.view)
        self.find_bar.setObjectName("mrFindBar")
        h = QHBoxLayout(self.find_bar)
        h.setContentsMargins(8, 6, 8, 6)
        h.setSpacing(4)
        self.find_input = QLineEdit()
        self.find_input.setFixedWidth(220)
        self.find_input.setClearButtonEnabled(True)
        self.find_input.returnPressed.connect(lambda: self._find(False))
        self.find_input.textChanged.connect(lambda _t: self._find(False))
        self.find_prev = QToolButton()
        self.find_prev.setText("▲")
        self.find_next = QToolButton()
        self.find_next.setText("▼")
        self.find_close = QToolButton()
        self.find_close.setText("✕")
        for btn, handler in ((self.find_prev, lambda: self._find(True)),
                             (self.find_next, lambda: self._find(False)),
                             (self.find_close, self._hide_find)):
            btn.setAutoRaise(True)
            btn.setFixedSize(24, 24)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(handler)
        h.addWidget(self.find_input)
        h.addWidget(self.find_prev)
        h.addWidget(self.find_next)
        h.addWidget(self.find_close)
        self._style_find_bar()
        self.find_bar.hide()
        return self.find_bar

    def _style_find_bar(self):
        """Vzhľad plávajúceho panela podľa aktuálnej témy."""
        if self.dark:
            bg, fg, bd = "#1c2128", "#e6edf3", "#30363d"
        else:
            bg, fg, bd = "#ffffff", "#1f2328", "#d0d7de"
        self.find_bar.setStyleSheet(
            f"#mrFindBar {{ background: {bg}; border: 1px solid {bd};"
            f" border-radius: 8px; }}"
            f"#mrFindBar QLineEdit {{ border: 1px solid {bd}; border-radius: 6px;"
            f" padding: 3px 6px; background: {bg}; color: {fg}; }}"
            f"#mrFindBar QToolButton {{ border: none; color: {fg};"
            f" border-radius: 4px; font-size: 12px; }}"
            f"#mrFindBar QToolButton:hover {{ background: {bd}; }}")

    def _position_find_bar(self):
        """Umiestni panel do pravého horného rohu zobrazenia."""
        if not getattr(self, "find_bar", None):
            return
        self.find_bar.adjustSize()
        margin = 14
        x = self.view.width() - self.find_bar.width() - margin
        self.find_bar.move(max(margin, x), margin)

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

        # Prečítať nahlas (ak sú dostupné hlasy Windows)
        if self.tts:
            self.speak_action = QAction(self)
            self.speak_action.setShortcut("Ctrl+R")
            self.speak_action.triggered.connect(self.speak_selection)
            tb.addAction(self.speak_action)

            self.stop_action = QAction(self)
            self.stop_action.triggered.connect(self.stop_speaking)
            tb.addAction(self.stop_action)

        tb.addSeparator()

        # Priblíženie / oddialenie textu (zmena veľkosti písma)
        self.zoom_out_action = QAction(self)
        self.zoom_out_action.setShortcut(QKeySequence.ZoomOut)
        self.zoom_out_action.triggered.connect(lambda: self._zoom(-0.1))
        tb.addAction(self.zoom_out_action)

        self.zoom_reset_action = QAction(self)
        self.zoom_reset_action.setShortcut("Ctrl+0")
        self.zoom_reset_action.triggered.connect(self._zoom_reset)
        tb.addAction(self.zoom_reset_action)

        self.zoom_in_action = QAction(self)
        self.zoom_in_action.setShortcut(QKeySequence.ZoomIn)
        self.zoom_in_action.triggered.connect(lambda: self._zoom(0.1))
        tb.addAction(self.zoom_in_action)
        # Ctrl+'=' ako alternatíva k Ctrl+'+' (bez shiftu)
        self._zoom_in_alt = QAction(self)
        self._zoom_in_alt.setShortcut("Ctrl+=")
        self._zoom_in_alt.triggered.connect(lambda: self._zoom(0.1))
        self.addAction(self._zoom_in_alt)

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
        if self.tts:
            self.speak_action.setText(self.t("read_aloud"))
            self.stop_action.setText(self.t("stop_reading"))
        self.zoom_in_action.setText(self.t("zoom_in"))
        self.zoom_out_action.setText(self.t("zoom_out"))
        self.zoom_reset_action.setText(self.t("zoom_reset"))
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
        # Konverzia Markdownu (najmä pri veľkých súboroch) beží na pozadí,
        # aby aplikácia počas renderovania nezamrzla.
        threading.Thread(target=self._md_worker, args=(path, text),
                         daemon=True).start()

    def _md_worker(self, path, text):
        try:
            md = markdown.Markdown(
                extensions=["extra", "codehilite", "sane_lists", "toc",
                            "admonition", "nl2br"],
                extension_configs={
                    "codehilite": {"guess_lang": False, "css_class": "codehilite"},
                    "toc": {"slugify": github_slugify},
                },
            )
            body = md.convert(text)
            toc = getattr(md, "toc_tokens", [])
        except Exception as exc:   # noqa: BLE001 – zobraz chybu namiesto pádu
            body = f"<h1>{self.t('read_error')}</h1><pre>{exc}</pre>"
            toc = []
        self._md_ready.emit(path, body, toc)

    def _on_md_ready(self, path, body, toc):
        if path != self.current_file:
            return   # medzičasom sa otvoril iný súbor – zahoď zastaraný výsledok
        self.current_body_html = body
        self._populate_outline(toc)
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
        # aplikuj uložené priblíženie na každú načítanú stránku
        self.view.setZoomFactor(self.zoom)
        # zachyť Ctrl+koliesko myši pre plynulé priblíženie (vnútorný widget
        # QWebEngineView vznikne až po prvom načítaní)
        if not self._wheel_filter_installed:
            fp = self.view.focusProxy()
            if fp is not None:
                fp.installEventFilter(self)
                self._wheel_filter_installed = True
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
        self._position_find_bar()
        self.find_bar.show()
        self.find_bar.raise_()
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
        posledného kliknutia (kurzora), inak od prvého viditeľného odseku.
        Pri PDF vytiahne text priamo z dokumentu (prípadne cez OCR)."""
        if not self.tts:
            return
        if self.current_kind == "pdf":
            self._speak_pdf()
        else:
            self.view.page().runJavaScript(SPEAK_JS, self._speak_text)

    # ---- PDF: text z dokumentu / OCR --------------------------------------- #
    def _speak_pdf(self):
        # Extrakcia textu (aj OCR) beží na pozadí – veľké PDF nezamrazí UI.
        threading.Thread(target=self._pdf_extract_worker,
                         args=(self.current_file,), daemon=True).start()

    def _pdf_extract_worker(self, path):
        text = self._pdf_text_layer(path)
        if text:
            self._ocr_ready.emit(text)
            return
        # žiadna textová vrstva -> skenované PDF -> OCR (ak je dostupné)
        if not (self.tesseract_path and path and fitz):
            self._ocr_ready.emit("")
            return
        try:
            import pytesseract  # noqa: F401
        except ImportError:
            self._ocr_ready.emit("")
            return
        self._status_signal.emit(self.t("ocr_running"))
        self._ocr_worker(path)   # sám vyšle _ocr_ready s výsledkom

    def _pdf_text_layer(self, path=None):
        path = path or self.current_file
        if not (fitz and path):
            return ""
        doc = None
        try:
            doc = fitz.open(path)
            parts = [p.get_text() for p in doc]
            return "\n".join(parts).strip()
        except Exception:
            return ""
        finally:
            if doc is not None:
                doc.close()

    def _ocr_worker(self, path):
        text = ""
        try:
            import io
            import pytesseract
            from PIL import Image
            pytesseract.pytesseract.tesseract_cmd = self.tesseract_path
            try:
                langs = set(pytesseract.get_languages(config=""))
            except Exception:
                langs = set()
            use = "+".join([l for l in ("slk", "eng") if l in langs]) or "eng"
            doc = fitz.open(path)
            out = []
            for page in doc:
                pix = page.get_pixmap(dpi=150)
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                out.append(pytesseract.image_to_string(img, lang=use))
            doc.close()
            text = "\n".join(out).strip()
        except Exception:
            text = ""
        self._ocr_ready.emit(text)

    def _on_ocr_ready(self, text):
        self.statusBar().clearMessage()
        if text and text.strip():
            self._speak_text(text)
        else:
            self.statusBar().showMessage(self.t("pdf_no_text"), 8000)

    def _speak_text(self, text):
        if not (self.tts and text and text.strip()):
            return
        self.stop_speaking()
        # vyber Windows hlas pre jazyk textu (ak existuje), inak predvolený
        code = self._detect_lang(text)
        if code:
            self._set_windows_voice(code)
        self.tts.say(text)
        self._reading = True

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

    def stop_speaking(self):
        self._reading = False
        if self.tts:
            self.tts.stop()

    def _on_tts_state(self, state):
        """Udržiava príznak čítania podľa stavu enginu – po dočítaní sa čítanie
        vypne, takže klik po skončení už nespustí čítanie odznova."""
        S = QTextToSpeech.State
        active = {S.Speaking, S.Paused}
        if hasattr(S, "Synthesizing"):
            active.add(S.Synthesizing)
        self._reading = state in active

    def _on_view_title(self, title):
        """Kliknutie v texte (signalizované cez titulok stránky). Ak práve
        prebieha čítanie, TTS preskočí na miesto kliknutia (kurzor)."""
        if not (title and title.startswith("mrjump:")):
            return
        if self._reading and self.tts:
            self.view.page().runJavaScript(SPEAK_JS, self._speak_text)

    # ---- priblíženie (veľkosť písma) --------------------------------------- #
    def _zoom(self, step):
        self.zoom = max(0.5, min(3.0, round(self.zoom + step, 2)))
        self.view.setZoomFactor(self.zoom)
        self.settings.setValue("zoom", self.zoom)

    def _zoom_reset(self):
        self.zoom = 1.0
        self.view.setZoomFactor(1.0)
        self.settings.setValue("zoom", 1.0)

    def eventFilter(self, obj, event):
        if (event.type() == QEvent.Wheel
                and event.modifiers() & Qt.ControlModifier):
            self._zoom(0.1 if event.angleDelta().y() > 0 else -0.1)
            return True
        if obj is self.view and event.type() == QEvent.Resize:
            self._position_find_bar()
        return super().eventFilter(obj, event)

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
        self._style_find_bar()
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
            self.resize(1400, 860)

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
