# 🔐 StuckAI — Security Architecture

This document describes how StuckAI protects its users, its backend and its business model. It covers the threat model, each security control in detail, the startup and request flows, operational procedures (key rotation, incident response) and — just as importantly — the **known limitations** of client-side security.

- [1. Security Philosophy](#1-security-philosophy)
- [2. Threat Model](#2-threat-model)
- [3. Startup Security Chain](#3-startup-security-chain)
- [4. Controls in Detail](#4-controls-in-detail)
  - [4.1 Signed Code-Integrity Manifest](#41-signed-code-integrity-manifest-anti-tamper)
  - [4.2 TLS Public-Key (SPKI) Pinning](#42-tls-public-key-spki-pinning)
  - [4.3 Build Allowlist & Forced Updates](#43-build-allowlist--forced-updates)
  - [4.4 Remote Maintenance Kill-Switch](#44-remote-maintenance-kill-switch)
  - [4.5 Anti-Replay Secure RPC](#45-anti-replay-secure-rpc)
  - [4.6 Server-Side Authorization (RLS + RPC)](#46-server-side-authorization-rls--security-definer-rpcs)
  - [4.7 Device Fingerprinting](#47-device-fingerprinting)
  - [4.8 Anti-Reverse-Engineering](#48-anti-reverse-engineering-native-compilation)
  - [4.9 Output Redaction](#49-output-redaction)
  - [4.10 Secret Management](#410-secret-management)
  - [4.11 Windows Process & Installer Hardening](#411-windows-process--installer-hardening)
- [5. Secure Request Lifecycle](#5-secure-request-lifecycle)
- [6. Threat → Control Matrix](#6-threat--control-matrix)
- [7. Operational Security](#7-operational-security)
- [8. Known Limitations & Residual Risk](#8-known-limitations--residual-risk)
- [9. Reporting a Vulnerability](#9-reporting-a-vulnerability)

---

## 1. Security Philosophy

StuckAI is a **paid, credit-based desktop application**. Every copy runs on a machine the developer does not control, where the user has administrator rights, a debugger and an intercepting proxy one download away. Three principles follow from that:

| Principle | What it means in StuckAI |
|---|---|
| **Never trust the client** | Credits, plan limits and API keys live on the server. The client *asks*; the server *decides*. |
| **Defense in depth** | No single control is relied upon. Integrity checks, pinning, allowlisting, anti-replay and server-side authorization each cover a different attack path, so bypassing one is not enough. |
| **Fail closed** | If a security check *cannot be performed* (network down, manifest missing, signature invalid, pin mismatch), the app refuses to run rather than running unprotected. |

Client-side controls are treated as **cost-raising** measures — they make tampering slow, noisy and non-scalable. **Server-side controls are the actual enforcement boundary.**

---

## 2. Threat Model

### Assets
- **Credits & plan entitlements** — directly convertible to money.
- **Third-party API keys** (LLM, image generation, stock media) — billed to the developer.
- **User accounts & personal data** (email, history, downloads).
- **Proprietary analysis logic and prompts.**
- **Backend infrastructure** (Supabase project, RPCs).

### Adversaries

| Adversary | Capability | Goal |
|---|---|---|
| **Curious / freeloading user** | Edits config files, uses Cheat Engine, runs a proxy | Free credits / Premium features |
| **Cracker** | Decompiles, patches binaries, redistributes cracked builds | Distribute a licence-free version |
| **Network attacker** | MITM on the same Wi-Fi, rogue CA, malicious proxy | Steal tokens, read/alter traffic |
| **Credential/key harvester** | Dumps strings, memory, logs | Extract API keys for reuse |
| **Account sharer** | Shares one paid account with many people | Avoid paying per seat |

### Out of scope
- A fully compromised OS with a kernel-level attacker (no user-mode software can defend against this).
- Compromise of Supabase or of third-party AI/media providers themselves.
- Physical access to the build machine holding the signing key.

---

## 3. Startup Security Chain

Implemented in [`app.py`](app.py). Each step runs **before** any UI is created; steps 3–5 terminate the process on failure.

```
            ┌─────────────────────────────────────┐
            │ python app.py / StuckAI.exe          │
            └──────────────┬──────────────────────┘
                           ▼
   1. install_global_no_console_patch()   hide child-process consoles
                           ▼
   2. install_print_redaction()           mask provider names & URLs in output
                           ▼
   3. run_integrity_check_or_exit()       signed manifest + SHA-256     ──✗──► exit
                           ▼
   4. enforce_maintenance_window_or_exit()  remote kill-switch          ──✗──► MaintenanceDialog / exit
                           ▼
   5. enforce_or_exit()                   TLS SPKI pin + BUILD_ID allowlist ──✗──► UpdateRequiredDialog / exit
                           ▼
   6. run_application()                   UI + login
```

The order is intentional:
- **Redaction is installed first** so that nothing printed by later checks can leak infrastructure details.
- **Integrity runs before any network trust decision**, so the code that performs pinning and allowlisting is itself verified as unmodified.
- **Pinning + allowlisting run before login**, so credentials are never sent over an unverified channel or from an unapproved build.

---

## 4. Controls in Detail

### 4.1 Signed Code-Integrity Manifest (Anti-Tamper)

**Files:** `security/bootstrap`, `security/integrity_manifest`, `security/integrity_hash`, [`tools/make_integrity_manifest.py`](tools/make_integrity_manifest.py), [`files.json`](files.json)

**Problem:** A cracker patches a `.pyd`, replaces a DLL, or edits `app.py` to skip a check, then redistributes the result.

**How it works**

1. **At build time** `make_integrity_manifest.py` walks every shipped file (`*.exe`, `**/*.pyd`, `**/*.dll`, `app.py`, UI files, assets …) and records its **SHA-256** (streamed in 1 MiB chunks).
2. The manifest payload is:
   ```json
   { "version": "<BUILD_ID>", "generated_at": "...Z", "alg": "SHA256",
     "kid": "k1", "files": [ { "path": "...", "sha256": "..." }, ... ],
     "signature": "<base64>" }
   ```
3. The signature is computed over the **canonical JSON of the payload without the `signature` field** — `json.dumps(sort_keys=True, separators=(",", ":"))`. Canonicalisation makes the signed bytes deterministic, so key order or whitespace can't be used to create a "different but equivalent" manifest.
4. Supported algorithms: **RSA PKCS#1 v1.5 + SHA-256** or **ECDSA P-256 + SHA-256**.
5. **At runtime** the client:
   - downloads the manifest from `INTEGRITY_MANIFEST_URL` (with a bounded-age local cache for resilience),
   - looks up the public key by **`kid`** in `INTEGRITY_PUBKEYS_JSON` — unknown key IDs are rejected,
   - verifies the signature, then the `version` against the running `BUILD_ID`,
   - hashes every listed file **in parallel** (`INTEGRITY_MAX_PARALLEL_HASH`) and compares digests,
   - **exits** on any missing file, mismatch, or verification error.
6. **Runtime re-verification:** `ensure_integrity_before_critical(max_age_seconds=300)` runs before every critical RPC (see [4.5](#45-anti-replay-secure-rpc)). If the last successful check is older than 5 minutes, it re-runs — so a binary patched *after* launch is caught before it can spend credits. A background re-check also runs every `INTEGRITY_PERIODIC_MINUTES`.
7. **No bypass switches:** legacy escape hatches such as a `DISABLE_INTEGRITY` environment variable or a `disable_integrity` marker file are explicitly ignored in production builds.

**Why asymmetric signatures?** A plain hash list could simply be regenerated by the attacker after patching. With a signature, producing a valid manifest requires the **private key, which never leaves the build machine**. The client only holds public keys.

**Why key IDs?** They enable **key rotation** without breaking installed clients: ship `k2` alongside `k1`, start signing with `k2`, then retire `k1`.

---

### 4.2 TLS Public-Key (SPKI) Pinning

**Files:** `logic/build_guard`, [`debug_tls_pins.py`](debug_tls_pins.py)

**Problem:** Standard TLS trusts *any* certificate signed by *any* CA in the OS trust store. An attacker who installs their own root CA (trivial with Burp Suite / Fiddler / mitmproxy on their own machine, or via malware on a victim's) can decrypt, read and modify all traffic — including tokens and RPC parameters.

**How it works**

1. Connect to the backend host and obtain the server's leaf certificate (DER).
2. Extract its **SubjectPublicKeyInfo** (the public key + algorithm identifier), DER-encode it.
3. `pin = base64(SHA-256(SPKI))`.
4. Compare with the pin(s) **embedded in the compiled `build_guard`** module.
5. Mismatch → log `SECURITY ALERT: TLS Pin mismatch` and **refuse to start**.

**Why SPKI instead of the whole certificate?** Certificates are renewed often (e.g. every 90 days); public keys can be kept across renewals. Pinning the key means routine renewals don't break the app, while a certificate issued by an attacker's CA — which necessarily has a *different* key — is rejected.

**Tooling:** `python debug_tls_pins.py <host>` prints the current SPKI pin of a live host, used to pre-compute the new pin before a planned key change. Debug output files (`tls_pin_debug_*.json`) are git-ignored.

**Defends against:** MITM on hostile networks, corporate/AV TLS interception, attackers inspecting the API surface with a proxy to craft forged requests.

---

### 4.3 Build Allowlist & Forced Updates

**Files:** `logic/build_guard`, `ui/update_required_dialog.py`

- Every release is stamped with a unique **`BUILD_ID`** (also recorded as the manifest `version`).
- On startup the client asks the server whether its `BUILD_ID` is on the **allowlist**.
- The same `BUILD_ID` is sent as `p_build_id` with **every** critical RPC, so the server re-checks it per request — an attacker can't just skip the startup check.
- Not allowlisted → **Update Required** dialog; the build cannot be used.

**Why it matters:** if a build is cracked or leaked, removing its ID from the allowlist **revokes it globally**, including copies already on users' disks. It also lets the developer force-retire builds with known vulnerabilities.

---

### 4.4 Remote Maintenance Kill-Switch

**Files:** `logic/maintenance_guard`, `ui/maintenance_dialog.py`

- A maintenance flag is read from the backend (via Supabase REST) on startup.
- When enabled, **every client** shows the Maintenance dialog and stops — no redeploy, no user action required.
- If the flag **cannot be read**, the app fails closed.

**Use cases:** a vulnerability is discovered in the field; a third-party API key is suspected compromised and must be rotated; abuse is detected and needs to be stopped while a fix ships.

---

### 4.5 Anti-Replay Secure RPC

**File:** [`logic/supabase_auth.py`](logic/supabase_auth.py) → `secure_rpc()`, `logic/session_token_service`

Credit deduction, AI image generation and other value-bearing operations are **never** performed through direct table writes. They go through server-side RPC functions, and `secure_rpc()` automatically attaches:

| Parameter | Purpose |
|---|---|
| `p_token` | **Short-lived session token (≤ 15 min)** issued by the `issue_session_token` RPC. Held **only in memory**, refreshed transparently when expired. Limits the window in which a stolen token is useful. |
| `p_build_id` | Lets the server reject requests from builds that are not on the allowlist. |
| `p_fp` | Hashed **device fingerprint** — binds the session token to the device it was issued to, so a token copied to another machine fails. |
| `p_nonce` | Random **UUIDv4**, single-use. The server records seen nonces and rejects duplicates → an intercepted request **cannot be replayed** to spend or farm credits twice. |
| `p_ts` | Millisecond **timestamp**. The server rejects requests outside its acceptance window, which bounds how long nonces must be stored and kills delayed replays. |

Additional guarantees in `secure_rpc()`:
- **Integrity first:** `ensure_integrity_before_critical(max_age_seconds=300)` runs before the call; failure returns `integrity_failed` and nothing is sent.
- **Fail-closed auth:** no session token after one refresh attempt → `auth_required`; no user JWT → `auth_jwt_missing`. The call is never made unauthenticated.
- **Two-credential model:** PostgREST is always authenticated with the user's **Supabase JWT** (identity for RLS), while the short-lived `p_token` proves a fresh, device-bound session. Stealing one without the other is insufficient.

---

### 4.6 Server-Side Authorization (RLS + SECURITY DEFINER RPCs)

- All tables are protected by **PostgreSQL Row Level Security**: a user's JWT can only read/write their own rows.
- Credit balances, plan limits, character limits and costs are **computed and enforced inside database functions**, not in the client. Changing a number in the UI, a config file or process memory changes nothing on the server.
- Sensitive mutations are exposed only through `SECURITY DEFINER` RPCs that validate token, nonce, timestamp, build ID and fingerprint *before* touching data.
- The **anon key** shipped in the client is public by design; it grants nothing beyond what RLS allows an anonymous/authenticated role.

This is the **real security boundary** of StuckAI. Everything in sections 4.1–4.4 and 4.7–4.11 exists to make attacking this boundary harder, noisier and non-scalable.

---

### 4.7 Device Fingerprinting

**File:** [`logic/utils.py`](logic/utils.py) → `generate_device_fingerprint()`

- Combines OS/platform details, CPU/architecture, MAC address, hostname, **Windows `MachineGuid`** (`HKLM\SOFTWARE\Microsoft\Cryptography`) and the **system volume serial number**.
- Serialised as sorted JSON and hashed with **SHA-256**; only the hash ever leaves the machine — **no raw hardware identifiers are transmitted** (privacy by design).
- Used for **device binding** (limits on devices per account) and to bind session tokens to a device (`p_fp`).

---

### 4.8 Anti-Reverse-Engineering (Native Compilation)

**File:** [`tools/build_logic_cython.py`](tools/build_logic_cython.py)

- All modules in `logic/` and `security/` are compiled with **Cython** into native C extensions (`.pyd`). The distributed build contains **no Python source** for them.
- Compiler hardening: `/O2 /Ob2` (MSVC) or `-O3 -fvisibility=hidden` (GCC/Clang) — aggressive inlining scatters logic and hides internal symbols.
- Cython directives `embedsignature=False`, `emit_code_comments=False`, `binding=False` strip function signatures, source comments and introspection metadata from the binary.
- Generated `.c` intermediates are **deleted** after compilation; symbol tables are removed with `strip`.
- Linker flags `/OPT:REF /OPT:ICF` drop unreferenced code and fold identical functions.
- Compiled modules are **listed in the integrity manifest**, so binary patching is detected (see 4.1).

Compared to plain `.pyc` (decompilable back to near-original source in seconds), this moves an attacker from "read the code" to "reverse-engineer optimised machine code".

---

### 4.9 Output Redaction

**File:** `logic/redaction`

- Wraps the global `print` so that **provider names, API hostnames and URLs are masked** before reaching the console or log files.
- Installed as the **second** startup step, before any network code runs.
- Prevents infrastructure fingerprinting via log files, bug-report screenshots or support tickets.

---

### 4.10 Secret Management

**Files:** `logic/api_key_service`, [`.env.example`](.env.example), [`.gitignore`](.gitignore)

- **Third-party API keys are never embedded in the client.** An authorised session fetches what it needs from the server; keys can be rotated server-side without shipping a new build.
- The only backend credential in the client is the **public Supabase anon key**, whose power is bounded by RLS.
- `.env`, `*.pem`, `*.key` and TLS debug dumps are **git-ignored**; the repository ships only `.env.example` with placeholders.
- The manifest signing key (`private.pem`) lives **only on the build machine**.

---

### 4.11 Windows Process & Installer Hardening

**Files:** [`logic/windows_subprocess.py`](logic/windows_subprocess.py), [`installer/StuckAI.iss`](installer/StuckAI.iss)

- `subprocess` is patched globally with `CREATE_NO_WINDOW` + `STARTF_USESHOWWINDOW`, and child stdin/stdout/stderr are redirected to `DEVNULL` unless explicitly captured. FFmpeg and other helpers never flash console windows that would reveal internal command lines.
- The Inno Setup installer places the app under **`Program Files`** (admin-only write) and grants `users-modify` **only** to the runtime data folders (`data`, `data\cache`, `data\cache\integrity`, `downloads`, `history`). Program binaries remain non-writable for standard users and for malware running as the user — complementing the integrity check.

---

## 5. Secure Request Lifecycle

Example: the user generates an AI image (costs credits).

```
 UI click
   │
   ▼
 secure_rpc("decrement_ai_image_count_secure", {...})
   │
   ├─► integrity re-check (if last check > 300 s)  ──✗──► "integrity_failed"
   ├─► get / refresh short-lived session token    ──✗──► "auth_required"
   ├─► attach p_token, p_build_id, p_nonce, p_ts (+ p_fp where the RPC requires it)
   ├─► ensure PostgREST uses the user's JWT       ──✗──► "auth_jwt_missing"
   │
   ▼  HTTPS (SPKI-pinned host)
 Supabase RPC (SECURITY DEFINER)
   ├─ JWT valid? user identified via RLS context
   ├─ session token valid, unexpired, bound to this user/device?
   ├─ build ID on allowlist?
   ├─ timestamp within window?  nonce never seen before?  → store nonce
   ├─ sufficient credits? → deduct atomically
   ▼
 result → UI
```

A captured copy of this request is useless shortly afterwards: the nonce is burned, the timestamp ages out, and the token expires within 15 minutes.

---

## 6. Threat → Control Matrix

| Threat | Primary control | Secondary controls |
|---|---|---|
| Patched / cracked binaries | Signed integrity manifest | Build allowlist, Cython compilation, periodic re-check |
| Runtime patching after launch | Pre-RPC integrity re-check (≤ 5 min) | Server-side enforcement |
| MITM / intercepting proxy | TLS SPKI pinning | Short-lived tokens, nonces |
| Leaked or outdated build | Build allowlist (startup + per-RPC) | Kill-switch |
| Zero-day in production | Remote maintenance kill-switch | Allowlist revocation |
| Request replay / credit farming | Nonce + timestamp | Short-lived device-bound token |
| Stolen session token | ≤ 15 min lifetime, device binding | JWT also required |
| Local credit/limit manipulation | Server-side RPC logic | RLS |
| Reading other users' data | Row Level Security | — |
| API key extraction | Server-brokered keys | Cython, redaction |
| Business-logic theft | Cython + strip | Source not in distribution |
| Infra disclosure via logs | Output redaction | — |
| Account sharing | Device fingerprint binding | Per-device limits |
| Writing into the install dir | Installer ACLs | Integrity check |

---

## 7. Operational Security

### Release checklist
1. Bump `BUILD_ID`.
2. `tools/build_logic_cython.py` → compile & stage (no `.py` / `.c` in output).
3. `tools/make_integrity_manifest.py` → hash & sign with the current `kid`.
4. Upload `files.json` to `INTEGRITY_MANIFEST_URL`.
5. Add the new `BUILD_ID` to the server allowlist.
6. Package with PyInstaller + Inno Setup.
7. Retire old build IDs once users have migrated.

### Signing-key rotation
1. Generate a new key pair (`k2`).
2. Ship a build whose `INTEGRITY_PUBKEYS_JSON` trusts both `k1` and `k2`.
3. Start signing manifests with `k2`.
4. Once all allowlisted builds trust `k2`, remove `k1`. If `k1` was **compromised**, remove it immediately and revoke builds that trust only `k1` via the allowlist.

### TLS key change
1. Pre-compute the new pin with `debug_tls_pins.py`.
2. Ship a build pinning **both** current and next keys.
3. Rotate the server key only after that build is the only one allowlisted.

### Incident response
1. **Enable maintenance mode** → all clients stop.
2. Rotate affected secrets server-side (API keys, signing key, Supabase keys).
3. Remove affected build IDs from the allowlist.
4. Ship a fixed build, allowlist it, disable maintenance mode.

---

## 8. Known Limitations & Residual Risk

Honest assessment — client-side protection is never absolute.

- **A determined reverse engineer with full control of their own machine can eventually bypass any client-side check** (e.g. patch the integrity verifier in memory with a debugger). The design accepts this: the client controls only raise the cost, while credits and keys remain protected by the server.
- **The fingerprint includes volatile fields** (OS version, hostname, Python version). Major Windows updates or a hostname change can alter the hash and trigger a device-binding re-check. Moving towards only stable identifiers (`MachineGuid`, volume serial) is planned.
- **The fingerprint falls back to a random value on error.** This prevents crashes, but on such machines device binding works like a new device on every run. The server should treat unexpected fingerprint churn as a signal.
- **Pinning is fail-closed**, so an unplanned server key change takes all clients offline until a new build ships. The rotation procedure in §7 exists to avoid this.
- **The startup sequence prints debug diagnostics** (including the observed SPKI pin) to stdout. This is harmless for security — the pin is derived from a public certificate — but it should be gated behind a debug flag in release builds.
- **Kill-switch and allowlist depend on backend availability.** Fail-closed means a backend outage is also a client outage — a deliberate trade-off of availability for integrity.

---

## 9. Reporting a Vulnerability

Please **do not open a public issue** for security problems. Contact the maintainer privately through the email on the GitHub profile, with:
- a description of the issue and its impact,
- steps to reproduce / proof of concept,
- the affected build ID, if known.

You will receive an acknowledgement, and coordinated disclosure will be arranged once a fix is available.
