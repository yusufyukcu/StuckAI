import sys
import subprocess
from typing import List, Optional


def run_hidden(command_args: List[str], timeout: Optional[int] = None, capture_output: bool = False) -> subprocess.CompletedProcess:

	if sys.platform.startswith("win"):
		startup_info = subprocess.STARTUPINFO()
		startup_info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
		creation_flags = subprocess.CREATE_NO_WINDOW
		kwargs = {
			"startupinfo": startup_info,
			"creationflags": creation_flags,
		}
		if capture_output:
			kwargs.update({"stdout": subprocess.PIPE, "stderr": subprocess.PIPE, "text": True})
		else:
			kwargs.update({"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL})
		return subprocess.run(command_args, timeout=timeout, **kwargs)
	else:
		if capture_output:
			return subprocess.run(command_args, timeout=timeout, capture_output=True, text=True)
		return subprocess.run(command_args, timeout=timeout)


def popen_hidden(command_args: List[str]) -> subprocess.Popen:

	if sys.platform.startswith("win"):
		startup_info = subprocess.STARTUPINFO()
		startup_info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
		creation_flags = subprocess.CREATE_NO_WINDOW
		return subprocess.Popen(command_args, startupinfo=startup_info, creationflags=creation_flags, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
	else:
		return subprocess.Popen(command_args)


def install_global_no_console_patch() -> None:
	"""Install global patch to prevent console windows, but only after core modules are loaded"""
	if not sys.platform.startswith("win"):
		return

	# Check if we're in a safe state to patch (avoid conflicts with asyncio, etc.)
	try:
		# Only patch if subprocess.Popen is still the original class
		if hasattr(subprocess.Popen, '__module__') and subprocess.Popen.__module__ == 'subprocess':
			# Store original Popen
			original_popen = subprocess.Popen

			def _popen_no_console(*args, **kwargs):
				startup_info = kwargs.get("startupinfo")
				if startup_info is None:
					startup_info = subprocess.STARTUPINFO()
					startup_info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
					kwargs["startupinfo"] = startup_info
				creation_flags = kwargs.get("creationflags", 0)
				creation_flags |= subprocess.CREATE_NO_WINDOW
				kwargs["creationflags"] = creation_flags
				# If caller did not request output capture, null the std streams to avoid implicit console allocation
				if "stdout" not in kwargs and "stderr" not in kwargs and "stdin" not in kwargs:
					kwargs.setdefault("stdin", subprocess.DEVNULL)
					kwargs.setdefault("stdout", subprocess.DEVNULL)
					kwargs.setdefault("stderr", subprocess.DEVNULL)
				return original_popen(*args, **kwargs)

			subprocess.Popen = _popen_no_console  # type: ignore[assignment]
			print("✅ Global subprocess patch installed successfully")
		else:
			print("⚠️  Subprocess already patched, skipping global patch")
	except Exception as e:
		print(f"⚠️  Could not install global subprocess patch: {e}")
		# Continue without patch - individual functions will still work


