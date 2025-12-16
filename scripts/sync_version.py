#!/usr/bin/env python3

import sys
import tomllib
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"

# File that contains the hard-coded version
TARGET_FILE = ROOT / "inception_reports" / "dashboard_version.py"
VERSION_VAR = "DASHBOARD_VERSION"

def main():
    if not PYPROJECT.exists():
        print("❌ pyproject.toml not found")
        sys.exit(1)

    if not TARGET_FILE.exists():
        print(f"❌ Target file not found: {TARGET_FILE}")
        sys.exit(1)

    with PYPROJECT.open("rb") as f:
        pyproject = tomllib.load(f)

    try:
        version = pyproject["project"]["version"]
    except KeyError:
        print("❌ project.version not found in pyproject.toml")
        sys.exit(1)

    text = TARGET_FILE.read_text(encoding="utf-8")

    pattern = rf'{VERSION_VAR}\s*=\s*["\'].*?["\']'
    replacement = f'{VERSION_VAR} = "{version}"'

    if not re.search(pattern, text):
        print(f"❌ {VERSION_VAR} not found in {TARGET_FILE}")
        sys.exit(1)

    new_text = re.sub(pattern, replacement, text)

    if new_text != text:
        TARGET_FILE.write_text(new_text, encoding="utf-8")
        print(f"✅ Synced {VERSION_VAR} -> {version}")
    else:
        print("ℹ️ Version already up to date")

if __name__ == "__main__":
    main()
