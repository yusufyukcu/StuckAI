#!/usr/bin/env python3
"""
Build Cython extension modules for all Python files under the `logic/` and
`security/` packages with strong optimization and place the compiled outputs
into a separate folder that mirrors the package layout (default:
build_cython/{logic,security}/*.pyd|.so).

Goals:
- Keep import paths identical (module names remain logic.*)
- Maximize optimization and hinder reverse engineering (within Cython's limits)
- Prepare for PyInstaller/Nuitka onefile packaging without including sources

Usage (PowerShell):
  py tools\build_logic_cython.py --out build_cython

Then package using the compiled outputs only (example, PyInstaller):
  py -m pip install Cython setuptools wheel
  pyinstaller -F -n StuckAI app.py --paths build_cython

To stage a full project tree without .py sources in logic/:
  py tools\build_logic_cython.py --out build_cython --stage-out stage
  # then build from `stage/` directory

Notes:
- We intentionally do NOT change runtime code; this is a build step only.
- `logic/__init__.py` and `security/__init__.py` are kept as Python files in
  the compiled tree to preserve package semantics.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path
from typing import List


def discover_logic_sources(root: Path) -> List[Path]:
    logic_dir = root / "logic"
    if not logic_dir.exists():
        raise SystemExit("logic/ directory not found")
    sources: List[Path] = []
    exclude_files = {"__init__.py", "supabase_auth.py"}
    for p in logic_dir.rglob("*.py"):
        if p.name in exclude_files:
            # Keep package init in Python and skip auth file from compilation
            continue
        if "__pycache__" in p.parts:
            continue
        sources.append(p)
    return sources


def discover_security_sources(root: Path) -> List[Path]:
    security_dir = root / "security"
    if not security_dir.exists():
        return []
    sources: List[Path] = []
    for p in security_dir.rglob("*.py"):
        if p.name == "__init__.py":
            continue
        if "__pycache__" in p.parts:
            continue
        sources.append(p)
    return sources


def build_extensions(out_dir: Path, sources: List[Path]) -> None:
    from setuptools import Extension
    from setuptools import setup
    from Cython.Build import cythonize
    import sys
    import sysconfig

    # Resolve Python headers/libs from the base interpreter (not venv-only)
    paths = sysconfig.get_paths()
    py_inc = Path(paths.get("include") or Path(sys.base_prefix) / "Include")
    py_plat_inc = paths.get("platinclude")
    py_plat_inc_p = Path(py_plat_inc) if py_plat_inc else None
    py_lib_dir = Path(sys.base_prefix) / "libs"
    py_lib_basename: str | None = None
    if os.name == "nt":
        try:
            major = sys.version_info.major
            minor = sys.version_info.minor
            preferred = py_lib_dir / f"python{major}{minor}.lib"
            if preferred.exists():
                py_lib_basename = preferred.stem  # e.g., python313
            else:
                # Fallback: pick first python*.lib
                for cand in sorted(py_lib_dir.glob("python*.lib")):
                    py_lib_basename = cand.stem
                    break
        except Exception:
            py_lib_basename = None

    module_names = []
    exts: List[Extension] = []

    # Compile/link flags per platform
    if os.name == "nt":
        extra_compile_args = ["/O2", "/Ob2", "/DNDEBUG"]
        # Avoid implicit wrong default lib (python313t.lib). Force correct one.
        disabled_default = []
        forced_default = []
        try:
            if py_lib_basename:
                forced_default = [f"/DEFAULTLIB:{py_lib_basename}"]
                disabled_default = [f"/NODEFAULTLIB:{py_lib_basename}t"]
        except Exception:
            pass
        extra_link_args = ["/OPT:REF", "/OPT:ICF", *forced_default, *disabled_default]
    else:
        extra_compile_args = ["-O3", "-fvisibility=hidden", "-fno-unwind-tables", "-fno-asynchronous-unwind-tables", "-DNDEBUG"]
        extra_link_args = ["-s"]
    for src in sources:
        # logic/foo.py -> logic.foo OR security/bar.py -> security.bar
        rel = src.with_suffix("")
        parts = rel.parts
        pkg = "logic" if "logic" in parts else ("security" if "security" in parts else None)
        if not pkg:
            raise SystemExit(f"Unsupported source root for {src}")
        idx = parts.index(pkg)
        mod_name = ".".join(parts[idx:])
        module_names.append(mod_name)
        exts.append(
            Extension(
                mod_name,
                sources=[str(src)],
                include_dirs=[
                    str(py_inc),
                    *( [str(py_plat_inc_p)] if py_plat_inc_p else [] ),
                ],
                library_dirs=[str(py_lib_dir)],
                libraries=([py_lib_basename] if py_lib_basename else []),
                extra_compile_args=extra_compile_args,
                extra_link_args=extra_link_args,
            )
        )

    compiler_directives = {
        "language_level": 3,
        "infer_types": True,
        "boundscheck": False,
        "wraparound": False,
        "nonecheck": False,
        "initializedcheck": False,
        "cdivision": True,
        "embedsignature": False,
        "binding": False,
        "optimize.use_switch": True,
        "optimize.unpack_method_calls": True,
        "emit_code_comments": False,
        "remove_unreachable": True,
    }

    print(f"Building {len(exts)} Cython extensions → {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)

    # Run an isolated setup() build placing outputs into out_dir
    setup(
        name="logic_cython_build",
        ext_modules=cythonize(
            exts,
            compiler_directives=compiler_directives,
            nthreads=max(1, os.cpu_count() // 2 or 1),
            annotate=False,
        ),
        script_args=["build_ext", f"--build-lib={str(out_dir)}", "--inplace"],
        options={"build_ext": {"build_lib": str(out_dir)}},
    )

    # Post-build hardening: remove generated C sources and strip symbols
    _cleanup_generated_c(sources)
    _cleanup_c_in_dir(out_dir)
    _strip_binaries(out_dir)


def copy_package_init(root: Path, out_dir: Path) -> None:
    # Ensure logic and security packages exist in out_dir with __init__.py present
    for pkg in ("logic", "security"):
        dst_pkg = out_dir / pkg
        dst_pkg.mkdir(parents=True, exist_ok=True)
        src_init = root / pkg / "__init__.py"
        if src_init.exists():
            shutil.copy2(src_init, dst_pkg / "__init__.py")
        else:
            (dst_pkg / "__init__.py").write_text("\n", encoding="utf-8")


def make_stage_tree(project_root: Path, compiled_root: Path, stage_root: Path) -> None:
    """Create a staging tree copying project, but replace logic/* and security/*
    with compiled outputs only.
    """
    if stage_root.exists():
        shutil.rmtree(stage_root)
    stage_root.mkdir(parents=True, exist_ok=True)

    # Copy all project files except logic/*.py and build folders
    def _should_skip(p: Path) -> bool:
        rel = p.resolve().relative_to(project_root.resolve())
        if rel.parts and rel.parts[0] in {"build", "build_cython", "dist", "__pycache__"}:
            return True
        if rel.parts and rel.parts[0] in {"logic", "security"} and p.suffix == ".py":
            return True
        return False

    for src in project_root.rglob("*"):
        if _should_skip(src):
            continue
        dst = stage_root / src.resolve().relative_to(project_root.resolve())
        if src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    # Replace logic package with compiled outputs
    stage_logic = stage_root / "logic"
    if stage_logic.exists():
        shutil.rmtree(stage_logic)
    shutil.copytree(compiled_root / "logic", stage_logic)
    # Replace security package with compiled outputs (if present)
    compiled_security = compiled_root / "security"
    if compiled_security.exists():
        stage_security = stage_root / "security"
        if stage_security.exists():
            shutil.rmtree(stage_security)
        shutil.copytree(compiled_security, stage_security)
    print(f"Staged project at: {stage_root}")


def _cleanup_generated_c(sources: List[Path]) -> None:
    for src in sources:
        for ext in (".c", ".cpp"):
            cfile = src.with_suffix(ext)
            try:
                if cfile.exists():
                    cfile.unlink()
            except Exception:
                pass


def _cleanup_c_in_dir(root: Path) -> None:
    try:
        for cfile in root.rglob("*.c"):
            try:
                cfile.unlink()
            except Exception:
                pass
        for cxx in root.rglob("*.cpp"):
            try:
                cxx.unlink()
            except Exception:
                pass
    except Exception:
        pass


def _strip_binaries(root: Path) -> None:
    import shutil
    import subprocess
    # Determine strip tool
    candidates = [
        shutil.which("llvm-strip"),
        shutil.which("strip"),
        shutil.which("llvm-strip.exe"),
        shutil.which("strip.exe"),
    ]
    tool = next((c for c in candidates if c), None)
    if not tool:
        return
    for ext in ("*.pyd", "*.so", "*.dll"):
        for binpath in root.rglob(ext):
            try:
                subprocess.run([tool, "-s", str(binpath)], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="build_cython", help="Output directory for compiled package root")
    ap.add_argument("--stage-out", default=None, help="Optional staging project root without logic .py sources")
    ap.add_argument("--only-utils", action="store_true", help="Compile only logic/utils.py (others skipped)")
    # Legacy flag kept for compatibility; security is now compiled by default.
    ap.add_argument("--include-security", action="store_true", help="[Deprecated] Security is compiled by default")
    args = ap.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    out_root = Path(args.out).resolve()
    out_logic_root = out_root  # we place logic/ under this root

    sources: List[Path] = []
    if args.only_utils:
        util = project_root / "logic" / "utils.py"
        if util.exists():
            sources.append(util)
    else:
        sources.extend(discover_logic_sources(project_root))

    # Always include security modules by default
    sources.extend(discover_security_sources(project_root))

    if not sources:
        print("No sources found to compile in logic/ or security/.")
        return

    copy_package_init(project_root, out_logic_root)
    build_extensions(out_logic_root, sources)

    if args.stage_out:
        make_stage_tree(project_root, out_logic_root, Path(args.stage_out).resolve())

    print("Cython build complete.")


if __name__ == "__main__":
    main()


