"""Download original Kaggle data locally; do not redistribute it in repositories."""
import hashlib
import io
import json
from pathlib import Path
import urllib.request
import zipfile

root = Path(__file__).resolve().parent.parent
destination = root / 'data/raw/kaggle_lead_scoring'
destination.mkdir(parents=True, exist_ok=True)
url = 'https://www.kaggle.com/api/v1/datasets/download/lakshmikalyan/lead-scoring-x-online-education'
request = urllib.request.Request(url, headers={'User-Agent': 'SMARTLEAD-educational-project/1.0'})
with urllib.request.urlopen(request, timeout=120) as response:
    archive = response.read()
with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
    for name in ['Leads X Education.csv', 'Leads X Education Data Dictionary.xlsx']:
        (destination / name).write_bytes(bundle.read(name))
csv_path = destination / 'Leads X Education.csv'
manifest = {'source': 'https://www.kaggle.com/datasets/lakshmikalyan/lead-scoring-x-online-education', 'sha256': hashlib.sha256(csv_path.read_bytes()).hexdigest(), 'usage_terms': 'Review the original dataset terms before use or redistribution.'}
(destination / 'download_manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print('Dataset and dictionary downloaded. Review source terms before use.')
