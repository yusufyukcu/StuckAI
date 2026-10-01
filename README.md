# 🎬 StuckAI

> **AI-powered script & scene analysis desktop app for video creators — built with a defense-in-depth client security architecture.**

[![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11%20x64-0078D6)](#-installation)
[![Python](https://img.shields.io/badge/python-3.10-3776AB)](#-tech-stack)
[![UI](https://img.shields.io/badge/UI-PyQt6-41CD52)](#-tech-stack)
[![Backend](https://img.shields.io/badge/backend-Supabase-3ECF8E)](#-tech-stack)
[![Security](https://img.shields.io/badge/security-defense--in--depth-critical)](SECURITY.md)

🇹🇷 Türkçe dokümantasyon: [README.tr.md](README.tr.md) · 🔐 Full security write-up: [SECURITY.md](SECURITY.md)

---

## 📑 Table of Contents

- [What is StuckAI?](#-what-is-stuckai)
- [Features](#-features)
- [Architecture](#-architecture)
- [Security at a Glance](#-security-at-a-glance)
- [Project Structure](#-project-structure)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Build & Release Pipeline](#-build--release-pipeline)
- [Tech Stack](#-tech-stack)
- [Note on Compiled Modules](#-note-on-compiled-modules)
- [Author](#-author)

---

## 🧠 What is StuckAI?

StuckAI takes a piece of text — a video script, a voice-over transcript, a blog article — and turns it into a **shot list**. It:

1. **Splits the text into main sections and sub-scenes**,
2. Generates a **title, summary, keywords, emotional tone and a visual prompt** for every scene,
3. Searches **stock image / stock video providers** for matching media,
4. Optionally **generates images with AI** when stock footage is not good enough,
5. Lets the user preview, pick and **download** everything in one place.

The result: a creator goes from "I have a script" to "I have the B-roll for every sentence" in minutes instead of hours.

StuckAI is a commercial, credit-based product (Free / Premium plans). Because it is distributed as a desktop binary onto machines the developer does not control, the project is also an exercise in **client-side hardening**: code-integrity verification, TLS public-key pinning, anti-replay RPCs, a remote kill-switch, build allowlisting and native compilation of business logic. These are summarised [below](#-security-at-a-glance) and documented in depth in [SECURITY.md](SECURITY.md).

---

## ✨ Features

### Smart scene analysis
- Automatic segmentation of long text into **sections → scenes**.
- Per-scene **title, summary, keywords, tone/emotion and image prompt**.
- "Smart scene analysis" decides whether a scene is better served by an **image or a video clip**.
- Character limits, plan type and credit balance are **validated on the server**, not in the client.

### Media discovery & generation
- Aggregated search across multiple stock image and stock video APIs.
- **AI image generation** with selectable aspect ratios (1:1, 16:9, 9:16, …).
- In-app video preview, playback and quality selection (FFmpeg-based).
- Background **lazy loading** and thumbnail generation keep the UI responsive.

### Download manager
- Single or bulk downloads with progress tracking.
- Download history, thumbnail previews and safe filename sanitisation.

### History & account
- Save and reopen previous analyses.
- Supabase-backed **sign-up / sign-in**, profile, plan (Free / Premium) and credit system.
- **Device binding** to prevent unauthorised multi-device account sharing.

### Modern UI
- Fully custom, animated PyQt6 interface (sidebar navigation, animated stat cards, drag-and-drop file input).
- Dedicated dialogs for **maintenance mode**, **forced update** and **no-connection** states.

---

## 🏗️ Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                       StuckAI (PyQt6 UI)                       │
│   ui/main_window.py · login_window.py · dialogs · QThreads     │
└────────────────┬───────────────────────────────────────────────┘
                 │
┌────────────────▼───────────────────────────────────────────────┐
│        logic/   business logic  (Cython-compiled .pyd)         │
│   scene_analysis · smart_scene_analysis · video_analysis       │
│   stock_api_service · leonardo_ai_service · cost_tracking      │
│   supabase_auth · session_token_service · api_key_service      │
└────────────────┬───────────────────────────────────────────────┘
                 │
┌────────────────▼───────────────────────────────────────────────┐
│        security/   integrity verification  (Cython .pyd)       │
│   bootstrap · integrity_manifest · integrity_hash              │
└────────────────┬───────────────────────────────────────────────┘
                 │   HTTPS  +  SPKI public-key pinning
┌────────────────▼───────────────────────────────────────────────┐
│  Supabase:  Auth · PostgREST · Row Level Security              │
│             SECURITY DEFINER RPCs (credits, session tokens,    │
│             maintenance flag, build allowlist, API key broker) │
└────────────────────────────────────────────────────────────────┘
```

**Design principle:** the client is treated as *untrusted*. Anything that has monetary value — credits, plan limits, API keys — lives on the server and is only reachable through authenticated, authorised, replay-protected RPCs. The client-side protections raise the cost of tampering; the server-side checks are what actually enforce the rules.

---

## 🔐 Security at a Glance

Before a single window is drawn, `app.py` runs a **fail-closed startup chain** — if any step cannot be completed, the process exits:

```
1. Subprocess patch     → hide console windows of child processes (FFmpeg, etc.)
2. Log redaction        → mask provider names / URLs in all printed output
3. Integrity check      → signed manifest + SHA-256 of every shipped file   (fail-closed)
4. Maintenance switch   → remote "stop everything" flag                    (fail-closed)
5. Build guard          → TLS SPKI pin + build-ID allowlist                (fail-closed)
6. UI starts
```

| # | Control | What it defends against |
|---|---------|-------------------------|
| 1 | **Signed integrity manifest** (RSA/ECDSA + SHA-256, key IDs, periodic re-check) | Cracked / patched binaries, swapped DLLs, runtime tampering |
| 2 | **TLS SPKI pinning** | Man-in-the-middle, intercepting proxies (Burp, Fiddler, mitmproxy), rogue root CAs |
| 3 | **Build allowlist + forced update** | Old, leaked or modified builds staying in circulation |
| 4 | **Remote maintenance kill-switch** | Zero-day in the field — every client can be stopped instantly |
| 5 | **Anti-replay secure RPC** (short-lived token, nonce, timestamp, build ID, device fingerprint) | Replaying captured requests to farm credits, token theft |
| 6 | **Server-side credit logic + Row Level Security** | Editing local values/memory to get free usage, reading other users' data |
| 7 | **Device fingerprinting** (hashed, never raw) | Account sharing across many machines |
| 8 | **Cython native compilation + symbol stripping** | Reading or trivially modifying business logic |
| 9 | **Log redaction** | Infrastructure details leaking through logs or screenshots |
| 10 | **Server-brokered API keys** | Third-party API keys being extracted from the binary |
| 11 | **Least-privilege installer ACLs** | Users / malware writing into the program directory |

👉 Every control — how it works, why it was chosen, threat model, and known limitations — is explained in **[SECURITY.md](SECURITY.md)**.

---

## 📁 Project Structure

```
StuckAI/
├── app.py                        # Entry point + security startup chain
├── StuckAI.spec                  # PyInstaller configuration
├── files.json                    # Signed integrity manifest
├── requirements.txt
├── run.bat                       # Windows launcher
├── install.py                    # Setup helper (creates .env, checks deps)
├── .env.example                  # Environment variable template
│
├── ui/                           # PyQt6 interface
│   ├── main_window.py            # Main window, pages, media cards
│   ├── login_window.py           # Sign-in / sign-up screen
│   ├── maintenance_dialog.py     # Maintenance-mode dialog
│   ├── update_required_dialog.py # Forced-update dialog (build not allowlisted)
│   ├── wifi_error_dialog.py      # No-connection dialog
│   ├── download_thread.py        # Background downloads
│   ├── smart_analysis_thread.py  # Background analysis
│   └── assets/                   # Icons, logos, animations
│
├── logic/                        # Business logic (mostly Cython .pyd)
│   ├── supabase_auth.py          # Auth + secure_rpc()
│   ├── session_token_service     # Short-lived session tokens
│   ├── build_guard               # TLS pinning + build allowlist
│   ├── maintenance_guard         # Remote kill-switch
│   ├── redaction                 # Output redaction
│   ├── api_key_service           # Server-brokered API keys
│   ├── scene_analysis / smart_scene_analysis / video_analysis
│   ├── stock_api_service / leonardo_ai_service
│   ├── cost_tracking_service / scene_cost_tracking_service
│   ├── utils.py                  # Device fingerprint, nonce, helpers
│   └── windows_subprocess.py     # Hidden-console subprocess patch
│
├── security/                     # Integrity verification (Cython .pyd)
│   ├── bootstrap                 # Startup & periodic checks
│   ├── integrity_manifest        # Manifest download + signature verification
│   └── integrity_hash            # Parallel SHA-256 hashing
│
├── tools/
│   ├── build_logic_cython.py     # Cython build + strip + source-free staging
│   └── make_integrity_manifest.py# Manifest generation & signing
│
├── debug_tls_pins.py             # Computes the SPKI pin of a live host
├── installer/StuckAI.iss         # Inno Setup installer script
└── fonts/                        # Poppins, Inter
```

---

## 🚀 Installation

> ⚠️ StuckAI is **fail-closed by design**: it will not start without a configured Supabase backend (with the required RPCs / tables), a matching TLS pin and a valid signed integrity manifest. Cloning the repo alone is not enough to run the full product.

**Requirements:** Windows 10/11 x64, Python 3.10, FFmpeg binaries.

```powershell
git clone https://github.com/<your-username>/StuckAI.git
cd StuckAI

python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

copy .env.example .env      # then fill in the values
```

Place the FFmpeg binaries (`ffmpeg.exe`, `ffprobe.exe` and their DLLs) in the project root — they are intentionally not committed because of their size. Download them from [ffmpeg.org](https://ffmpeg.org/download.html).

```powershell
run.bat
# or
python app.py
```

---

## ⚙️ Configuration

| Variable | Description |
|---|---|
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_ANON_KEY` | Supabase **anon (public)** key — safe to ship; RLS enforces access |
| `APP_BASE_URL` | Base URL of the companion web app (account / billing pages) |
| `INTEGRITY_MANIFEST_URL` | Where the signed `files.json` is downloaded from |
| `INTEGRITY_PUBKEYS_JSON` | JSON map of trusted public keys by key ID, e.g. `{"k1": "-----BEGIN PUBLIC KEY-----..."}` |
| `INTEGRITY_PERIODIC_MINUTES` | Interval for background integrity re-verification |

Never commit `.env` or any private key — both are covered by `.gitignore`.

---

## 📦 Build & Release Pipeline

```powershell
# 1) Compile critical packages to native extensions and produce a source-free staging tree
py tools\build_logic_cython.py --out build_cython --stage-out stage

# 2) Create a signing key pair (once, on the build machine only)
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out private.pem
openssl rsa -in private.pem -pubout -out public.pem

# 3) Hash every shipped file and sign the manifest
python tools\make_integrity_manifest.py --root . --kid k1 --private-key .\private.pem --output .\files.json

# 4) Bundle into a single executable
pyinstaller StuckAI.spec

# 5) Build the Windows installer
iscc installer\StuckAI.iss
```

After a release, the new `BUILD_ID` is added to the server-side allowlist and old/compromised IDs can be removed, which forces their users onto the update dialog.

> 🔑 `private.pem` must **never** leave the build machine. If it leaks, rotate to a new key ID (`k2`), ship the new public key, and remove `k1` from `INTEGRITY_PUBKEYS_JSON`.

---

## 🛠️ Tech Stack

| Area | Technology |
|---|---|
| UI | PyQt6, PyQt6-QtSvg |
| Backend / Auth | Supabase (Auth, PostgREST, Row Level Security, RPC) |
| AI | OpenAI, Leonardo AI, Whisper |
| Media | FFmpeg, OpenCV, Pillow |
| Cryptography | `cryptography` (RSA / ECDSA / SHA-256), SPKI pinning |
| Build / Distribution | Cython, PyInstaller, Inno Setup |

---

## 🧩 Note on Compiled Modules

Most modules in `logic/` and `security/` are committed as **compiled `.pyd` extensions** (CPython 3.10, Windows x64) rather than Python source. This is deliberate: it is the same artefact that ships to users, and keeping the proprietary analysis logic and security internals out of the public tree is part of the hardening strategy. The open `.py` files (`supabase_auth.py`, `utils.py`, `windows_subprocess.py`, the UI and tooling) show how the compiled modules are wired together.

---

## 👤 Author

**Yusuf Eren Yükcü**

© 2025 StuckAI — All rights reserved. This repository is published for portfolio and review purposes; no license to use, copy or redistribute the software is granted.
