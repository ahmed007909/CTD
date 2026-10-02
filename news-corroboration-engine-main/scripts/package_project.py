"""Build a portable source ZIP, excluding credentials, caches and collected news."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

root = Path(__file__).resolve().parents[1]
target = root / "output" / "news_corroboration_engine.zip"
target.parent.mkdir(exist_ok=True)
files = [
    root / name
    for name in (
        "README.md",
        "VALIDATION.md",
        "SECURITY.md",
        "pyproject.toml",
        "requirements-tested.txt",
        ".env.example",
        ".gitignore",
        "run.ps1",
    )
]
for folder in ("news_engine", "tests", "scripts"):
    files.extend(p for p in (root / folder).rglob("*") if p.is_file() and "__pycache__" not in p.parts)
with ZipFile(target, "w", ZIP_DEFLATED) as archive:
    for path in sorted(files):
        archive.write(path, Path("news_corroboration_engine") / path.relative_to(root))
with ZipFile(target) as archive:
    assert archive.testzip() is None
print(target)
print(f"{len(files)} files; {target.stat().st_size:,} bytes")
