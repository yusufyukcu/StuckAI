#!/usr/bin/env python3
"""
Generate integrity manifest (files.json) and sign it with your private key.

Usage (PowerShell examples):
  # 1) Generate keys once (RSA)
  # openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out private.pem
  # openssl rsa -in private.pem -pubout -out public.pem

  # 2) Make manifest (customize includes)
  python tools/make_integrity_manifest.py \
      --root . \
      --include "bin/StuckAI.exe" \
      --include "core/*.pyd" --include "core/*.so" --include "core/*.dll" \
      --include "assets/prompts.json" \
      --kid k1 \
      --private-key ./private.pem \
      --output ./files.json

Notes:
 - Version defaults to logic.build_guard.BUILD_ID if available, else --version.
 - The signature is computed over canonical JSON of the manifest WITHOUT the 'signature' field.
 - Canonicalization uses separators=(",", ":"), sort_keys=True.
"""

from __future__ import annotations

import argparse
import base64
import glob
import hashlib
import json
import os
from pathlib import Path
from typing import Iterable, List, Tuple
from datetime import datetime, timezone


EXCLUDE_DIRS = {
    "cache", "logs", "downloads", "thumbnails", "temp",
    str(Path("data/cache")),
}


def _norm_rel(root: Path, p: Path) -> str:
    rel = p.resolve().relative_to(root.resolve())
    return rel.as_posix()


def _collect_files(root: Path, includes: List[str]) -> List[Path]:
    seen: set[str] = set()
    out: List[Path] = []
    for pattern in includes:
        for match in root.glob(pattern):
            if match.is_dir():
                # Expand recursively
                for sub in match.rglob("*"):
                    if sub.is_file() and not _is_excluded(root, sub):
                        key = str(sub.resolve())
                        if key not in seen:
                            seen.add(key)
                            out.append(sub)
            else:
                if match.is_file() and not _is_excluded(root, match):
                    key = str(match.resolve())
                    if key not in seen:
                        seen.add(key)
                        out.append(match)
    return out


def _is_excluded(root: Path, p: Path) -> bool:
    try:
        rel = p.resolve().relative_to(root.resolve())
    except Exception:
        return True
    parts = set(rel.parts)
    return any(part in EXCLUDE_DIRS for part in parts)


def _sha256_stream(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _canonical_without_sig(payload: dict) -> bytes:
    data = {
        k: v for k, v in payload.items() if k != "signature"
    }
    return json.dumps(data, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _sign(private_key_pem: bytes, message: bytes) -> str:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding, ec
    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    key = load_pem_private_key(private_key_pem, password=None)
    if key.__class__.__name__.endswith("RSAPrivateKey"):
        sig = key.sign(message, padding.PKCS1v15(), hashes.SHA256())
        return base64.b64encode(sig).decode("utf-8")
    if key.__class__.__name__.endswith("EllipticCurvePrivateKey"):
        sig = key.sign(message, ec.ECDSA(hashes.SHA256()))
        return base64.b64encode(sig).decode("utf-8")
    raise RuntimeError("Unsupported key type for signing")


def detect_version_fallback(default: str | None = None) -> str:
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "build_guard", str(Path("logic/build_guard.py").resolve())
        )
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)  # type: ignore
            val = getattr(mod, "BUILD_ID", None)
            if isinstance(val, str) and val.strip():
                return val
    except Exception:
        pass
    return default or "unknown"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".", help="Project/build root (relative paths computed from here)")
    ap.add_argument("--include", action="append", default=[], help="File path or glob to include; can be repeated")
    ap.add_argument("--version", default=None, help="Manifest version/build id. Default: logic.build_guard.BUILD_ID")
    ap.add_argument("--kid", required=True, help="Key id")
    ap.add_argument("--private-key", required=True, help="PEM private key path")
    ap.add_argument("--output", default="files.json", help="Output manifest path")
    args = ap.parse_args()

    root = Path(args.root).resolve()
    version = args.version or detect_version_fallback()

    includes = args.include or [
        # Reasonable defaults for compiled builds; customize as needed.
        "*.exe",
        "**/*.pyd", "**/*.so", "**/*.dll",
        "assets/prompts.json",
    ]

    paths = _collect_files(root, includes)
    files = [
        {"path": _norm_rel(root, p), "sha256": _sha256_stream(p)} for p in paths
    ]

    payload = {
        "version": version,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "alg": "SHA256",
        "files": files,
        "kid": args.kid,
    }

    canon = _canonical_without_sig(payload)
    sig_b64 = _sign(Path(args.private_key).read_bytes(), canon)
    payload["signature"] = sig_b64

    out_path = Path(args.output)
    out_path.write_text(json.dumps(payload, separators=(",", ":"), sort_keys=True), encoding="utf-8")
    print(f"Wrote manifest: {out_path}")
    print(f"Files included: {len(files)}")


if __name__ == "__main__":
    main()



