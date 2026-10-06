"""Prepare sanitized source ZIP and standalone React backend handoff snapshot."""
import hashlib
import argparse
import json
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / 'output'
FULL = OUTPUT / 'smartlead-django'
HANDOFF = OUTPUT / 'smartlead-react-handoff'
EXCLUDED_DIRS = {'.git', 'my_venv', '.venv', '__pycache__', 'media', 'staticfiles', 'output', '.publish', 'data'}
EXCLUDED_NAMES = {'.env', 'LOCAL_ACCESS.txt'}


def allowed(relative):
    return not any(part in EXCLUDED_DIRS for part in relative.parts) and relative.name not in EXCLUDED_NAMES and relative.suffix not in {'.pyc', '.sqlite3'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--refresh', action='store_true', help='Refresh previously generated sanitized snapshots.')
    options = parser.parse_args()
    OUTPUT.mkdir(exist_ok=True)
    for target in [FULL, HANDOFF]:
        if target.exists() and not options.refresh:
            raise SystemExit('Snapshot exists; choose a fresh output directory rather than overwriting.')
        target.mkdir(exist_ok=True)
    for source in ROOT.rglob('*'):
        relative = source.relative_to(ROOT)
        if source.is_file() and allowed(relative):
            destination = FULL / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
    for folder in ['backend', 'ml', 'scripts', 'react-handoff']:
        shutil.copytree(FULL / folder, HANDOFF / folder, dirs_exist_ok=True)
    (HANDOFF / 'docs').mkdir(exist_ok=True)
    for name in ['API_CONTRACT.md', 'SETUP.md', 'IMPLEMENTATION_DECISIONS.md', 'VERIFICATION_CURRENT.md', 'openapi.yaml']:
        shutil.copy2(FULL/'docs'/name, HANDOFF/'docs'/name)
    shutil.copytree(FULL/'postman', HANDOFF/'postman', dirs_exist_ok=True)
    shutil.copy2(FULL/'.gitignore', HANDOFF/'.gitignore')
    (HANDOFF/'README.md').write_text((ROOT/'react-handoff/README.md').read_text(encoding='utf-8'), encoding='utf-8')
    archive = OUTPUT/'SMARTLEAD_Django_Complete.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for source in FULL.rglob('*'):
            if source.is_file():
                bundle.write(source, Path('SMARTLEAD')/source.relative_to(FULL))
    with zipfile.ZipFile(archive) as bundle:
        assert bundle.testzip() is None
        names = bundle.namelist()
        assert any(name.endswith('business/models.py') for name in names)
        assert any(name.endswith('business/home.html') for name in names)
        assert any(name.endswith('SmartLead_Project_Report.pdf') for name in names)
        assert not any(Path(name).name in EXCLUDED_NAMES or Path(name).suffix == '.sqlite3' for name in names)
    manifest = {'zip': archive.name, 'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'file_count': len(names), 'excluded': 'Credentials, environments, local databases, raw dataset and uploads', 'full_snapshot': str(FULL), 'react_snapshot': str(HANDOFF)}
    (OUTPUT/'delivery_manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
