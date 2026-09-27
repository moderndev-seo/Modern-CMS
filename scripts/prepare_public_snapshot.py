"""Export current tracked/source files without local history or private artifacts."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

root = Path(__file__).resolve().parents[1]
out = root / "output" / "team-repository" / "Modern-CMS"
if out.exists():
    raise SystemExit(f"Snapshot already exists; inspect it before preparing another: {out}")
paths = subprocess.check_output(
    ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=root
).decode().split("\0")
paths += [".env.docker.example"]
excluded_roots = {".git", "reference", "output", ".codex", ".agents"}
excluded_parts = {"node_modules", "__pycache__", ".venv", ".svelte-kit", ".pytest_cache", ".ruff_cache"}
excluded_suffixes = {".pdf", ".pptx", ".pem", ".key", ".sqlite3", ".dump", ".log", ".pyc"}
manifest = []
for name in sorted(set(paths)):
    if not name:
        continue
    relative = Path(name)
    source = root / relative
    if relative.parts[0] in excluded_roots or excluded_parts.intersection(relative.parts):
        continue
    if relative.suffix.lower() in excluded_suffixes or source.name == '.DS_Store':
        continue
    if source.name.startswith('.env') and not source.name.endswith('.example'):
        continue
    if not source.is_file() or source.is_symlink():
        continue
    if name in ('.github/workflows/publish.yml', '.github/workflows/tag-release.yml'):
        relative = Path('docs/upstream-workflows') / relative.name
    target = out / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    if relative.parts[:2] == ('docs', 'modern-practice'):
        target.write_text(target.read_text().replace('seo@modernpractice.com', 'admin@localhost'))
    manifest.append({'path': str(relative), 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
(out.parent / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(f'Prepared {len(manifest)} files in {out}')
print('Excluded private configuration, data exports, internal PDFs/decks and all Git history.')
