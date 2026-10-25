import json, sys
from pathlib import Path
from collections import Counter
sys.path.insert(0, 'scripts')
import bridge as b

count = 0
def verify(path, sha):
    global count
    path = Path(path).resolve()
    assert path.is_relative_to(b.ROOT.resolve())
    assert path.is_file() and b.digest(path.read_bytes()) == sha, path
    count += 1

snapshot = b.source_snapshot()
campaigns = []
for path in sorted((b.ROOT/'evidence').glob('*/manifest.json')):
    m = b.verify_evidence(path)
    campaigns.append({'path': path.relative_to(b.ROOT).as_posix(), 'passed': m['passed'],
        'current_sources': m['source']['sha256'] == snapshot['sha256'], 'integrity': 'verified'})
    count += 1 + len(m['artifacts'])
for path in (b.ROOT/'evidence').glob('*/SHA256SUMS'):
    for line in path.read_text(encoding='utf-8').splitlines():
        sha, name = line.split('  ', 1)
        verify(path.parent/name, sha)
old = b.ROOT/'evidence/finalization/artifacts.json'
for name, sha in b.read_json(old).items():
    verify(old.parent/name, sha)
old = b.ROOT/'evidence/cli-test-fd030c4/index.json'
for name, sha in b.read_json(old)['artifacts'].items():
    verify(old.parent/name, sha)
for item in b.read_json(b.ROOT/b.read_json(b.LOCAL/'ci-final.json')['index_ref'])['files']:
    verify(b.ROOT/item['path'], item['sha256'])
external = b.read_json(b.ROOT/'evidence/diagnostics-20261024/index.json')['external_artifacts']
for item in external:
    path = b.ROOT/item['origin']
    assert path.stat().st_size == item['bytes']
    verify(path, item['sha256'])
statuses = Counter(b.effective_status(c, snapshot) for c in b.registry()['claims'])
assert statuses == {'vérifié_local':21,'vérifié_besu_local':5,'bloqué':2}
current = [c for c in campaigns if c['current_sources']]
assert len(current) == 3 and all(c['passed'] for c in current)
report = {'utc':b.utc(),'passed':True,'source_sha256':snapshot['sha256'],
    'scope':'Intégrité des campagnes, index historiques, archive CI extraite et instantanés externes. Cet audit ne se valide pas lui-même ; son index de livraison porte son empreinte.',
    'verified_hashes':count,'campaigns':campaigns,'current_campaigns':len(current),
    'external_artifacts':len(external),'external_bytes':sum(i['bytes'] for i in external),'claims':dict(statuses)}
b.write_json(b.ROOT/'evidence/finalization-b97c541/delivery-integrity.json',report)
print(json.dumps({k:v for k,v in report.items() if k not in ('campaigns','scope')},ensure_ascii=False,indent=2))
