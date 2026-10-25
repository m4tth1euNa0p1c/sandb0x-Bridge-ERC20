"""Vérification finale des rapports, liens servis et état observé ; aucun transfert."""
import json,sys,urllib.request,shutil
from collections import Counter
sys.path.insert(0,'scripts')
import bridge as b
import bridge_runtime as rt

out=b.ROOT/'evidence/finalization'
out.mkdir(exist_ok=True)
snapshot=b.source_snapshot()
campaigns=[]
for path in sorted((b.ROOT/'evidence').glob('*/manifest.json')):
    m=b.verify_evidence(path)
    campaigns.append({'path':path.relative_to(b.ROOT).as_posix(),'integrity':'verified',
      'passed':m['passed'],'current_sources':m['source']['sha256']==snapshot['sha256']})
claims=[{'id':c['id'],'status':b.effective_status(c,snapshot)} for c in b.registry()['claims']]
counts=dict(Counter(c['status'] for c in claims))
assert counts=={'vérifié_local':21,'vérifié_besu_local':5,'bloqué':2},counts
assert all(c['status'] in ('vérifié_local','vérifié_besu_local','bloqué') for c in claims)
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
http=[]
for port in (18080,18081):
    for path in ('/','/resultats/','/status/','/claims.yaml'):
        with opener.open(f'http://127.0.0.1:{port}{path}',timeout=10) as response:
            raw=response.read()
            assert response.status==200 and len(raw)>100
            http.append({'url':f'http://127.0.0.1:{port}{path}','status':response.status,'bytes':len(raw),'sha256':b.digest(raw)})
states={}
for name in ('local-fast','local-besu'):
    state=rt.read_status(b,name)
    assert state['ready'] is True and state['stale'] is False
    assert state['reconciliation']['state']=='balanced' and state['reconciliation']['difference']=='0'
    assert state['transfers']['counts']['intervention_required']==0
    assert all(n['paused'] is False for n in state['networks'])
    states[name]=state
shutil.copyfile(b.LOCAL/'doctor.json',out/'doctor-delivery.json')
report={'utc':b.utc(),'code_commit':b.run(['git','rev-parse','HEAD'])['stdout'],
 'source_sha256':snapshot['sha256'],'scope':'Instantané de livraison ; les services et données peuvent changer après cette date.',
 'passed':True,'claims':claims,'counts':counts,'campaign_integrity':campaigns,'served_pages':http,'states':states,
 'external_integration':'Sepolia et TELA non exécutés ; activation refusée.',
 'remaining':'VM dédiée, filtrage hôte effectif, dossier TELA/Sepolia et moyens de test.'}
b.write_json(out/'delivery.json',report)
print(json.dumps({'passed':True,'statuses':counts,'http_pages':len(http),'both_reconciliations':'balanced','source_sha256':snapshot['sha256']},ensure_ascii=False,indent=2))
