# Vendored uv for Offline Windows Setup

This directory contains a Windows x64 `uv.exe` fallback so Hermes can bootstrap
Python and dependencies in restricted Windows environments where downloading uv
after an error would be slow or impossible.

Bundled file:

- `uv.exe`
- Version: `0.11.14`
- Platform artifact: `uv-x86_64-pc-windows-msvc.zip`
- Source: https://github.com/astral-sh/uv/releases/tag/0.11.14
- Download URL: https://releases.astral.sh/github/uv/releases/download/0.11.14/uv-x86_64-pc-windows-msvc.zip
- ZIP SHA256: `52ba5d19409aaa688a8a1a6ec8dfb6a4817230d20186e75f4006105c3e39a846`
- Extracted `uv.exe` SHA256: `442b73298cf8648217e5bc232588bb1067f98ea5b40beea18e43c9c7929c020c`

Do not remove this file unless the Windows offline bootstrap path is replaced by
another committed binary fallback.
