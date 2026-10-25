import json, sys
sys.path.insert(0,'scripts')
import bridge as b

original=b.run_secret_scanner
def limited(directory,target,*,timeout,check=True):
    return original(directory,target,timeout=2,check=check)
b.run_secret_scanner=limited
started=b.utc()
source_commit=b.run(['git','rev-parse','HEAD'])['stdout']
try:
    b.scan_secrets()
    raise AssertionError('Le témoin aurait dû expirer')
except b.BridgeError as error:
    assert '(124)' in str(error), str(error)
scans=[r for r in b.RECORDS if r['command'][:2]==['docker','run']]
assert len(scans)==1 and scans[0]['exit_code']==124
command=scans[0]['command']
name=command[command.index('--name')+1]
cleanup=[r for r in b.RECORDS if r['command']==['docker','rm','--force',name]]
assert len(cleanup)==1 and cleanup[0]['exit_code']==0, cleanup
inspection=b.run(['docker','container','inspect',name],check=False)
assert inspection['exit_code']==1 and 'No such' in inspection['stderr']
report={'started_utc':started,'ended_utc':b.utc(),'passed':True,
  'source_commit':source_commit,
  'scope':'Injection réelle de timeout à deux secondes sur la copie versionnable, sans modifier le budget normal de cinq minutes.',
  'expected':'Refus 124, suppression du seul conteneur de scan lancé, absence après nettoyage.',
  'observed':'Les trois assertions passent ; le scanner incomplet ne valide pas les sources.',
  'source':b.source_snapshot(),'commands':b.RECORDS}
target=b.ROOT/'evidence/scanner-timeout-20261025'/ (sys.argv[1] if len(sys.argv)>1 else 'witness.json')
assert not target.exists(), 'Préserver le témoin précédent'
b.write_json(target,report)
print(json.dumps({'passed':True,'timeout_exit':scans[0]['exit_code'],'cleanup_exit':cleanup[0]['exit_code'],'container_absent':True},indent=2))
