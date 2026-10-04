"""Start OneAquaHealth using the repository's virtual environment, when present."""

import os
from pathlib import Path
import sys


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    interpreter = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not interpreter.is_file():
        interpreter = Path(sys.executable)
    os.chdir(root)
    os.execv(str(interpreter), [str(interpreter), "-m", "dashboard.launcher", *sys.argv[1:]])
