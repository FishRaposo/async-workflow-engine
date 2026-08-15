"""Build the wheel and import its vendored namespace from a clean virtualenv."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import venv
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENDORED_INIT = "workflow_engine/internal/vendor_core/__init__.py"


def _python_in(virtualenv: Path) -> Path:
    if sys.platform == "win32":
        return virtualenv / "Scripts" / "python.exe"
    return virtualenv / "bin" / "python"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="awfe-package-") as temporary:
        work = Path(temporary)
        wheel_dir = work / "wheel"
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "wheel",
                "--no-deps",
                "--no-cache-dir",
                "--no-build-isolation",
                "--wheel-dir",
                str(wheel_dir),
                ".",
            ],
            cwd=ROOT,
            check=True,
        )
        wheel = next(wheel_dir.glob("async_workflow_engine-*.whl"), None)
        if wheel is None:
            raise RuntimeError("Wheel build did not produce async_workflow_engine")
        with zipfile.ZipFile(wheel) as archive:
            if VENDORED_INIT not in archive.namelist():
                raise RuntimeError(f"Wheel is missing {VENDORED_INIT}")

        virtualenv = work / "venv"
        venv.EnvBuilder(with_pip=True, clear=True).create(virtualenv)
        python = _python_in(virtualenv)
        subprocess.run(
            [str(python), "-m", "pip", "install", "--no-deps", str(wheel)],
            check=True,
        )
        subprocess.run(
            [
                str(python),
                "-I",
                "-c",
                (
                    "import importlib.util; "
                    "assert importlib.util.find_spec('shared_core') is None; "
                    "import workflow_engine; "
                    "import workflow_engine.internal.vendor_core"
                ),
            ],
            cwd=work,
            check=True,
        )
    print("Wheel content and isolated imports passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
