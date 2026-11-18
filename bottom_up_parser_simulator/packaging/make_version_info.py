"""Generate a Windows version resource file (``version_info.txt``).

Reads ``version.json`` and writes ``packaging/version_info.txt`` in the format
consumed by PyInstaller's ``version=`` argument so the packaged executable
carries proper version metadata in its file properties.

Usage:
    python packaging/make_version_info.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = ROOT / "version.json"
OUTPUT = Path(__file__).resolve().parent / "version_info.txt"


def _version_tuple(version: str) -> tuple:
    parts = (version.split(".") + ["0", "0", "0", "0"])[:4]
    numeric = []
    for part in parts:
        digits = "".join(ch for ch in part if ch.isdigit())
        numeric.append(int(digits) if digits else 0)
    return tuple(numeric)


def build_version_info() -> str:
    """Return the contents of ``version_info.txt``.

    Returns:
        The version resource template as a string.
    """
    data = {}
    if VERSION_FILE.exists():
        data = json.loads(VERSION_FILE.read_text(encoding="utf-8"))
    version = str(data.get("version", "1.0.0"))
    build = str(data.get("build", "0"))
    release_date = str(data.get("release_date", ""))
    file_version = _version_tuple(version)
    file_version_str = ".".join(str(n) for n in file_version)
    prod_version_str = version

    return f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={file_version},
    prodvers={file_version},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=0
  ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'Compiler Construction'),
         StringStruct(u'FileDescription', u'ParseCraft'),
         StringStruct(u'FileVersion', u'{file_version_str}'),
         StringStruct(u'InternalName', u'ParseCraft'),
         StringStruct(u'LegalCopyright', u'Compiler Construction'),
         StringStruct(u'OriginalFilename', u'ParseCraft.exe'),
         StringStruct(u'ProductName', u'ParseCraft'),
         StringStruct(u'ProductVersion', u'{prod_version_str}'),
         StringStruct(u'Build', u'{build}'),
         StringStruct(u'ReleaseDate', u'{release_date}')])
      ]),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"""


def main() -> None:
    """Write ``version_info.txt`` next to this script."""
    content = build_version_info()
    OUTPUT.write_text(content, encoding="utf-8")
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()