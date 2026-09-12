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
- 📝 **PDF text mode** (`Ctrl+T`) — re-flows a PDF into clean text (headings, code
  blocks with their indentation, lists, images) rendered like Markdown. The native
  PDF viewer is a closed plugin, so in text mode you get what it can't offer:
  **click anywhere and read aloud from there**, text selection and the **Contents**
  sidebar. The choice is remembered.
- 🗂️ **Tabs** — every document opens in its own tab (like a browser or Notepad++).
  Opening a file from Explorer reuses the running window and adds a **new tab**
  instead of launching another copy of the app (single-instance).
- 🔁 **Convert between formats** — export any open document **to Markdown, PDF or HTML**.
- 🔎 **Full-text search** in the document (Ctrl+F).
- 🔊 **Read aloud (offline TTS)** — reads the selected text, or starts from where you
  last clicked (the cursor); auto-detects the text language and picks a matching
  **built-in Windows voice**. While it's reading, **click anywhere in the text to
  jump** and continue from there. Works in Markdown, HTML and in PDFs opened in
  **text mode** (`Ctrl+T`); the native PDF viewer can only read from the start.
  All offline and free.
- 🔍 **Zoom** — change the text size with `Ctrl` `+` / `Ctrl` `-`, `Ctrl` `0` to
  reset, or `Ctrl` + mouse wheel. The zoom level is remembered between sessions.
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
- Python 3.9+ — **optional**: if you don't have it, the installer downloads it
  from [python.org](https://www.python.org/downloads/) and installs it for you
  (per-user, no admin rights needed)

Dependencies (installed automatically):

| Package | Purpose |
|---------|---------|
| [PySide6](https://pypi.org/project/PySide6/) | GUI + embedded web/PDF view |
| [Markdown](https://pypi.org/project/Markdown/) | Markdown → HTML |
| [Pygments](https://pypi.org/project/Pygments/) | Code syntax highlighting |
| [PyMuPDF](https://pypi.org/project/PyMuPDF/) | PDF text/outline & PDF conversion |
| [markdownify](https://pypi.org/project/markdownify/) | HTML → Markdown conversion |
| [langdetect](https://pypi.org/project/langdetect/) | Detects text language for read-aloud voice |
| [pytesseract](https://pypi.org/project/pytesseract/) | OCR for scanned/image PDFs (needs Tesseract) |

## Installation

```powershell
git clone https://github.com/<your-username>/m-reader.git
cd m-reader
powershell -ExecutionPolicy Bypass -File install.ps1
```

The installer (no admin rights needed, everything under `HKCU`):

1. Finds a usable Python — and if there isn't one, downloads and installs it
   from python.org for the current user only.
2. Installs the Python dependencies from `requirements.txt`.
3. Generates the app icon.
4. Builds a no-console launcher (`M Reader.exe`, or `run_hidden.vbs` as fallback).
5. Registers `.md`, `.markdown`, `.html`, `.htm` and `.pdf` to open with M Reader.
6. Adds an **M Reader** shortcut to the Start Menu.

Installer switches:

| Switch | Effect |
|--------|--------|
| `-Yes` | Don't ask before installing Python (for scripted / unattended runs) |
| `-NoPythonInstall` | Never install Python; fail with instructions if none is found |
| `-PythonVersion <v>` | Which Python to download (default `3.13.15`) |

> **The Microsoft Store version of Python will not work**, and the installer
> deliberately skips it. Its `site-packages` sits under a ~145-character path
> (`…\Packages\PythonSoftwareFoundation.Python.3.13_…\LocalCache\…`), and because
> PySide6 ships deeply nested files, pip blows past the Windows 260-character
> path limit with `OSError: [Errno 2] No such file or directory` unless long-path
> support is enabled (which needs admin rights). The installer therefore installs
> a regular Python into `%LOCALAPPDATA%\Programs\Python`, where the path is short.

> **Note on the default app:** Windows protects the default-app choice, so it may
> ask you to confirm once. If a file doesn't open in M Reader automatically:
> right-click it → **Open with** → **Choose another app** → pick **M Reader** and
> tick *Always use this app*.

> **Keep the project folder where it is.** The launcher and the file associations
> point at `pythonw.exe` and `m_reader.py` by absolute path. If you move or
> rename the folder, just run `install.ps1` again.

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
| `Ctrl+O` | Open file (in a new tab) |
| `Ctrl+Shift+O` | Open folder |
| `Ctrl+W` | Close current tab |
| `Ctrl+F` | Find in text |
| `Ctrl+T` | PDF: switch between the native viewer and text mode |
| `Ctrl+R` | Read aloud (selection, or from where you're reading) |
| `Ctrl` `+` / `Ctrl` `-` | Zoom text in / out (also `Ctrl` + mouse wheel) |
| `Ctrl+0` | Reset zoom |
| `Ctrl+D` | Toggle dark mode |
| `Ctrl+B` | Toggle sidebar |

Use the **Export** button to save the current document as Markdown, PDF or HTML.

> **Read-aloud voices:** M Reader uses the built-in Windows voices. Add more
> languages under **Settings → Time & language → Speech → Manage voices**.
>
> **Scanned-PDF OCR (optional):** run `install_extras.ps1` to enable reading of
> **scanned/image PDFs** (**Tesseract OCR** + Slovak data):
> ```powershell
> powershell -ExecutionPolicy Bypass -File install_extras.ps1
> ```
> For PDFs with a text layer it reads the text directly; for scanned/image PDFs it
> runs OCR automatically (if Tesseract is installed).

> **PDF outline:** in the native PDF viewer use its own outline/bookmarks panel.
> In **text mode** (`Ctrl+T`) the sidebar **Contents** tab is filled from the
> headings found in the PDF (or from page numbers when it has none).

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
python -m pip uninstall PySide6 Markdown Pygments PyMuPDF markdownify langdetect pytesseract
```

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `pip install` fails with `OSError: [Errno 2] No such file or directory` and a hint about long paths | You're on the Microsoft Store Python. Run `install.ps1` — it skips that one and installs a proper Python. |
| Installer aborts with `Unexpected token` / garbled accented characters | The `.ps1` files must be saved as **UTF-8 with BOM**; Windows PowerShell 5.1 otherwise reads them as ANSI. |
| Installer says it can't find Python right after installing it | Close the terminal, open a new one and run `install.ps1` again — the new `PATH` only reaches fresh processes. |
| `pip install` fails with *Access is denied* | Your Python lives in a system-wide location. Either reinstall it per-user, or run `python -m pip install --user -r requirements.txt`. |
| Nothing opens on double-click | Right-click → **Open with** → **Choose another app** → **M Reader** → *Always use this app*. |
| Leftover `.venv\` folder in the project | Older versions of the installer created one. It's unused now — `Remove-Item -Recurse -Force .venv` frees ~700 MB. |

## Project structure

```
m-reader/
├─ m_reader.py        # the application
├─ install.ps1        # installer (Python + deps + file associations + shortcut)
├─ install_extras.ps1 # optional: Tesseract OCR for scanned PDFs
├─ uninstall.ps1      # removes associations & shortcut
├─ build_exe.ps1      # builds a standalone .exe (PyInstaller)
├─ make_icon.ps1      # generates the app icon
├─ requirements.txt   # Python dependencies
├─ ukazka.md          # sample Markdown file
└─ assets/            # icon & screenshot for this README
```

## License

Released under the [MIT License](LICENSE).
