# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Mascote: a Windows-only desktop pet (PySide6) that sits in a screen corner, with a local LLM (Gemma 2 9B via llama.cpp, or optionally Ollama). Code, comments, UI text and commits are in Brazilian Portuguese — keep it that way. Product intent and decisions live in `docs/design.md` (and `docs/plano.md`).

## Commands

- Run from source: `.venv\Scripts\python.exe -m mascote` (or `run_mascote.py`)
- Tests: `.venv\Scripts\python.exe -m pytest tests -q`; single test: `... -m pytest tests/test_agenda.py::nome_do_teste`
- Build installer: `.\build.ps1 -Versao X.Y.Z` (runs tests → PyInstaller onedir → strips unused Qt DLLs → Inno Setup 6 builds `dist\MascoteSetup.exe` and an isolated `dist\Mascote-teste-setup.exe`). Add `-Publicar` to create GitHub release `vX.Y.Z` on `samuelikz/mascote`.
- `build.ps1` overwrites `mascote/versao.py` — don't edit it by hand.
- A running Mascote/llama-server holds the GPU; kill them before running the real-IA tests (build.ps1 does this).

## Architecture

- `__main__.py`: single-instance lock (`QLockFile` in data dir); `--baixar-modelo` mode is invoked by the installer to download the IA with a progress window (`baixar_ui.py`).
- `app.py` (`App`): orchestrator — timers (lunch, hunger, nap/idle, reminders), context menu, wires `Pet` (drawing/animation, `pet.py`) and `Balao` (speech/chat bubble, `balao.py`) to the IA and storage.
- IA: `ia.py` — `ServidorIA` spawns `llama-server` on demand on a random port with a secret, inside a Windows Job Object so it dies with the app, and shuts it down when idle; `ClienteOllama` is the alternative; `criar_ia(prefs)` picks one; `PonteIA` bridges worker threads to Qt signals. Prompt construction and parsing of model output (reminder extraction, memory) is in `prompts.py`.
- `baixar.py`: downloads llama.cpp + model from the project's `ia-v1` GitHub release (model split in parts due to 2 GB limit), falls back to original sources or copies from a local Ollama; verifies SHA-256.
- `atualizar.py` / `atualizar_ui.py`: checks GitHub releases for a newer version than `versao.VERSAO` and runs the new installer.
- Storage (`config.py`): JSON files in `%LOCALAPPDATA%\<identidade>\dados` (reminders via `agenda.py`, memories via `memoria.py`); preferences in the registry `HKCU\Software\<identidade>`. `identidade()` derives from the install folder name so the test install ("MascoteTeste") never mixes with the real one.
- `janelas.py`: Win32 ctypes helpers (fullscreen detection, idle seconds).
- `claude.py`: optional Claude Code integration — merges hooks into `~/.claude/settings.json` that run `Mascote.exe --claude <evento>`; that writes `claude.txt` in the data dir, which `App` watches (`QFileSystemWatcher`).
- Chat replies stream (`PonteIA.pedaco` → `Balao.escrever_rascunho`); reminder extraction is constrained by `prompts.ESQUEMA_LEMBRETE` (llama-server `response_format` / Ollama `format`). Context is 8192 tokens; `prompts.LIMITE`/`ORCAMENTO` are sized for it.
- On/off features (iniciativa, voz, area_transferencia) and appearance (cor, acessorio) are keys in `config.PADROES` (config.json), toggled from the Ajustes menu; the tray icon is the way back from "Esconder" and "Modo fantasma".

## Testing notes

- `tests/conftest.py` forces `QT_QPA_PLATFORM=offscreen` and redirects `MASCOTE_DADOS` (temp dir) and `MASCOTE_REGISTRO` (throwaway registry key) per test — use these env vars rather than touching real data.
- Tests needing the real model/Ollama are `skipif`-guarded and auto-skip when unavailable.
