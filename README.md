<div align="center">

<img src="assets/icon.png" width="120" alt="M Reader logo">

# M Reader

A lightweight, good-looking **document reader & converter for Windows**.
Open **Markdown**, **HTML** and **PDF** files, read them rendered like on GitHub,
convert between formats, search the text, and set it as your default viewer.

<img src="assets/screenshot.png" width="800" alt="M Reader screenshot">

</div>

## Features

- 📄 **Reads Markdown, HTML and PDF** in one window (GitHub-style Markdown rendering,
  native PDF viewer, direct HTML rendering).
- 🔁 **Convert between formats** — export any open document **to Markdown, PDF or HTML**.
- 🔎 **Full-text search** in the document (Ctrl+F).
- 🔊 **Read aloud (offline TTS)** — reads the selected text, or starts from where you
  last clicked (the cursor); auto-detects the text language and picks a matching
  voice. Uses the built-in Windows voices, and falls back to
  [eSpeak NG](https://github.com/espeak-ng/espeak-ng) for languages Windows doesn't
  have installed (e.g. Slovak). All offline and free.
- 🎨 **Syntax highlighting** for Markdown code blocks (Pygments).
- 🌗 **Light / dark theme** — toggling keeps your scroll position.
- 🌍 **Multi-language UI** — English (default), Slovak, Russian, Spanish.
- 🗂️ **Switchable sidebar** — folder **Files** or a document **Outline** (table of
  contents) you can click to jump around, like a PDF reader.
- 🔗 **TOC links that work** for files from any generator (fuzzy anchor matching).
- 🪟 **Windows integration** — set as the default app for `.md`, `.html` and `.pdf`,
  with a Start Menu shortcut and no console window.

## Requirements

- Windows 10 / 11
- [Python 3.9+](https://www.python.org/downloads/) on `PATH`

Dependencies (installed automatically):

| Package | Purpose |
|---------|---------|
| [PySide6](https://pypi.org/project/PySide6/) | GUI + embedded web/PDF view |
| [Markdown](https://pypi.org/project/Markdown/) | Markdown → HTML |
| [Pygments](https://pypi.org/project/Pygments/) | Code syntax highlighting |
| [PyMuPDF](https://pypi.org/project/PyMuPDF/) | PDF text/outline & PDF conversion |
| [markdownify](https://pypi.org/project/markdownify/) | HTML → Markdown conversion |
| [langdetect](https://pypi.org/project/langdetect/) | Detects text language for read-aloud voice |

## Installation

```powershell
git clone https://github.com/<your-username>/m-reader.git
cd m-reader
powershell -ExecutionPolicy Bypass -File install.ps1
```

The installer (no admin rights needed, everything under `HKCU`):

1. Installs the Python dependencies from `requirements.txt`.
2. Generates the app icon.
3. Creates a no-console launcher (`run_hidden.vbs`).
4. Registers `.md`, `.markdown`, `.html`, `.htm` and `.pdf` to open with M Reader.
5. Adds an **M Reader** shortcut to the Start Menu.

> **Note on the default app:** Windows protects the default-app choice, so it may
> ask you to confirm once. If a file doesn't open in M Reader automatically:
> right-click it → **Open with** → **Choose another app** → pick **M Reader** and
> tick *Always use this app*.

### Alternative: standalone `.exe`

Prefer a self-contained executable that doesn't need Python installed? Build one
with PyInstaller:

```powershell
powershell -ExecutionPolicy Bypass -File build_exe.ps1            # folder with M Reader.exe (recommended)
powershell -ExecutionPolicy Bypass -File build_exe.ps1 -OneFile   # a single .exe
```

The result lands in `dist\M Reader\M Reader.exe` (or `dist\M Reader.exe` with
`-OneFile`). Because it bundles Qt WebEngine, the output is large (~200–300 MB).

## Usage

- **Double-click** a `.md`, `.html` or `.pdf` file, or
- launch **M Reader** from the Start Menu, then open a file/folder.

| Shortcut | Action |
|----------|--------|
| `Ctrl+O` | Open file |
| `Ctrl+Shift+O` | Open folder |
| `Ctrl+F` | Find in text |
| `Ctrl+R` | Read aloud (selection, or from where you're reading) |
| `Ctrl+D` | Toggle dark mode |
| `Ctrl+B` | Toggle sidebar |

Use the **Export** button to save the current document as Markdown, PDF or HTML.

> **Read-aloud voices:** M Reader first uses the natural voices installed in Windows
> (**Settings → Time & language → Speech → Manage voices**). For languages Windows
> doesn't offer (e.g. Slovak on managed PCs), install **eSpeak NG** and M Reader will
> use it automatically:
> ```powershell
> winget install eSpeak-NG.eSpeak-NG
> ```
> eSpeak NG is offline and free; its voice is robotic but reads the language correctly.

> **PDF outline:** for PDFs, use the PDF viewer's own outline/bookmarks panel; the
> sidebar **Contents** tab is used for Markdown and HTML documents.

Run it directly without installing:

```powershell
python m_reader.py path\to\file.pdf
```

## Uninstall

```powershell
powershell -ExecutionPolicy Bypass -File uninstall.ps1
```

Removes the file associations and the Start Menu shortcut. To also remove the
Python packages:

```powershell
python -m pip uninstall PySide6 Markdown Pygments PyMuPDF markdownify
```

## Project structure

```
m-reader/
├─ m_reader.py        # the application
├─ install.ps1        # installer (deps + file associations + shortcut)
├─ uninstall.ps1      # removes associations & shortcut
├─ build_exe.ps1      # builds a standalone .exe (PyInstaller)
├─ make_icon.ps1      # generates the app icon
├─ requirements.txt   # Python dependencies
├─ ukazka.md          # sample Markdown file
└─ assets/            # icon & screenshot for this README
```

## License

Released under the [MIT License](LICENSE).
