"""Intervention ponctuelle sur UN transfert Anvil de test identifié ; pas un mécanisme automatique.
La transaction signée reste en PostgreSQL et n'est jamais extraite par ce script.
Le relayer existant revérifie source, reçu, processed et nonce avant rediffusion.
"""
import json,sys,time,shutil
from pathlib import Path
sys.path.insert(0,'scripts')
import bridge as b
import bridge_runtime as rt

TRANSFER='0x6236e0d1c2f4491dfa94dadab8d3081b7589506d9ddffa66392d990f8a5e1091'
name='local-fast';assert b.profile(name,runnable=True)['test_only'] is True
p=b.profile(name);d=b.read_json(b.runtime(name)/'deployment.json')
folder=b.ROOT/'evidence/restart-incident-20261024';folder.mkdir(exist_ok=True)
assert not (folder/'recovery.json').exists(), 'Intervention déjà consignée : ne pas la rejouer'
shutil.copyfile(__file__,folder/'operator-recovery.py')
report={'started_utc':b.utc(),'source_commit':b.run(['git','rev-parse','HEAD'])['stdout'],
        'source_sha256':b.source_snapshot()['sha256'],'script_sha256':b.digest(Path(__file__).read_bytes()),
        'scope':'Intervention opérateur explicite sur le seul transfert nommé, après diagnostic de disparition de l’effet et du reçu. Aucune nouvelle signature, aucun nonce nouveau, aucune émission compensatoire.',
        'passed':False,'checks':[]}
def check(id,condition,observed):
    report['checks'].append({'id':id,'passed':bool(condition),'observed':observed,'utc':b.utc()})
    assert condition,id
pg=b.container_id(name,'postgres')
def sql(statement):
    report.setdefault('database_procedures',[]).append(statement)
    return b.run(['docker','exec','-i',pg,'psql','-X','-q','-A','-t','-v','ON_ERROR_STOP=1','-U','sandbox_admin','-d','bridge'],stdin_text=statement)['stdout']
def row():
    return json.loads(sql("SELECT row_to_json(t) FROM (SELECT id,source_chain,destination_chain,source_block,source_block_hash,source_tx,recipient,source_nonce,amount,destination_signer,state,error_code,attempts,destination_nonce,destination_hash,destination_block,destination_block_hash,encode(sha256(convert_to(signed_raw,'UTF8')),'hex') AS payload_sha256 FROM bridge.transfers WHERE id='"+TRANSFER+"') t;"))
try:
    b.compose(name,['--profile','bridge','stop','--timeout','10','relayer'],timeout=45)
    active=b.compose(name,['--profile','bridge','ps','--status','running','--quiet','relayer'])['stdout']
    check('relayer_stopped',not active,active)
    before=row();report['before']=before
    check('expected_intervention',before['state']=='intervention_required' and before['error_code']=='destination_effect_lost_after_policy_finality',before['error_code'])
    for i,c in enumerate(p['chains']):
        n=d['networks'][i];identity=b.chain_observation(c)
        check('identity_'+n['name'],identity['genesis_hash'].lower()==n['genesisHash'].lower(),identity)
        for label in ('token','bridge'):
            code=b.rpc(c['rpc_host'],'eth_getCode',[n[label+'Address'],'latest'])
            check('code_'+n['name']+'_'+label,rt.keccak(b,c,code).lower()==n[label+'CodeHash'].lower(),n[label+'CodeHash'])
    si=next(i for i,n in enumerate(d['networks']) if n['chainId']==before['source_chain']);di=1-si
    sc=p['chains'][si];dc=p['chains'][di];sn=d['networks'][si];dn=d['networks'][di]
    source=b.rpc(sc['rpc_host'],'eth_getTransactionReceipt',[before['source_tx']]);report['source_receipt']=source
    canonical=b.rpc(sc['rpc_host'],'eth_getBlockByNumber',[hex(before['source_block']),False])
    check('source_burn_canonical',source is not None and source['status']=='0x1' and source['blockHash']==canonical['hash']==before['source_block_hash'],canonical)
    check('source_policy_finalized',int(b.rpc(sc['rpc_host'],'eth_blockNumber'),16)>=before['source_block']+sc['finality']['depth'],before['source_block'])
    signature='TransferInitiated(bytes32,uint256,address,address,address,address,address,uint256,uint256)'
    topic=rt.keccak(b,sc,signature.encode().hex())
    logs=[l for l in source['logs'] if l['address'].lower()==sn['bridgeAddress'].lower() and l['topics'][0]==topic and l['topics'][1]==TRANSFER]
    expected_data='0x'+rt.encode(['address','address','address','address','uint256','uint256'],[before['recipient'],sn['tokenAddress'],dn['tokenAddress'],dn['bridgeAddress'],before['source_nonce'],before['amount']])
    check('exact_burn_parameters',len(logs)==1 and logs[0]['data'].lower()==expected_data.lower() and int(logs[0]['topics'][2],16)==dn['chainId'],logs)
    calculated=rt.call(b,dc,dn['bridgeAddress'],'computeTransferId(uint256,address,uint256,address,address,address,uint256,uint256,address)',[sn['chainId'],sn['bridgeAddress'],dn['chainId'],dn['bridgeAddress'],sn['tokenAddress'],dn['tokenAddress'],before['source_nonce'],before['amount'],before['recipient']])
    check('domain_identifier',calculated.lower()==TRANSFER,calculated)
    receipt=b.rpc(dc['rpc_host'],'eth_getTransactionReceipt',[before['destination_hash']])
    known=b.rpc(dc['rpc_host'],'eth_getTransactionByHash',[before['destination_hash']])
    processed=int(rt.call(b,dc,dn['bridgeAddress'],'processed(bytes32)',[TRANSFER]),16)
    latest=int(b.rpc(dc['rpc_host'],'eth_getTransactionCount',[dn['signerAddress'],'latest']),16)
    pending=int(b.rpc(dc['rpc_host'],'eth_getTransactionCount',[dn['signerAddress'],'pending']),16)
    check('effect_and_transaction_absent',receipt is None and known is None and processed==0,{'receipt':receipt,'transaction':known,'processed':processed})
    check('same_nonce_still_free',latest==pending==before['destination_nonce'],{'latest':latest,'pending':pending,'reserved':before['destination_nonce']})
    pending_rows=int(sql("SELECT count(*) FROM bridge.transfers WHERE state NOT IN ('destination_finalized','rejected') AND id<>'"+TRANSFER+"';"))
    check('no_other_pending_transfer',pending_rows==0,pending_rows)
    balance_before=int(rt.call(b,dc,dn['tokenAddress'],'balanceOf(address)',[before['recipient']]),16)
    statement=("UPDATE bridge.transfers SET state='destination_prepared',error_code=NULL,destination_block=NULL,destination_block_hash=NULL,next_attempt=now(),updated_at=now() WHERE id='"+TRANSFER+"' AND state='intervention_required' AND error_code='destination_effect_lost_after_policy_finality' AND destination_nonce="+str(before['destination_nonce'])+" AND destination_hash='"+before['destination_hash']+"' AND encode(sha256(convert_to(signed_raw,'UTF8')),'hex')='"+before['payload_sha256']+"' RETURNING id;")
    updated=sql(statement)
    check('single_guarded_transition',updated==TRANSFER,updated)
    b.compose(name,['--profile','bridge','start','relayer'],timeout=45)
    deadline=time.monotonic()+120
    while time.monotonic()<deadline:
        after=row()
        if after['state']=='destination_finalized':break
        time.sleep(1)
    report['after']=after
    check('finalized_by_existing_processor',after['state']=='destination_finalized',after['state'])
    check('same_signature_nonce_and_hash',all(after[k]==before[k] for k in ('payload_sha256','destination_nonce','destination_hash')),{'payload_sha256':after['payload_sha256'],'nonce':after['destination_nonce'],'transaction_hash':after['destination_hash']})
    receipt=rt.receipt(b,dc,after['destination_hash']);report['recovered_receipt']=receipt
    check('receipt_canonical',b.rpc(dc['rpc_host'],'eth_getBlockByNumber',[receipt['blockNumber'],False])['hash']==receipt['blockHash'],receipt['blockHash'])
    completion_topic=rt.keccak(b,dc,b'TransferCompleted(bytes32,address,uint256)'.hex())
    completions=b.rpc(dc['rpc_host'],'eth_getLogs',[{'address':dn['bridgeAddress'],'fromBlock':hex(dn['startBlock']),'toBlock':'latest','topics':[completion_topic,TRANSFER]}])
    check('one_completion',len(completions)==1 and int(completions[0]['data'],16)==int(before['amount']) and ('0x'+completions[0]['topics'][2][-40:]).lower()==before['recipient'].lower(),completions)
    balance_after=int(rt.call(b,dc,dn['tokenAddress'],'balanceOf(address)',[before['recipient']]),16)
    check('single_exact_credit',balance_after-balance_before==int(before['amount']),{'before':str(balance_before),'after':str(balance_after),'amount':str(before['amount'])})
    deadline=time.monotonic()+30
    while time.monotonic()<deadline:
        status=rt.read_status(b,name)
        if status['reconciliation']['state']=='balanced' and status['transfers']['counts']['intervention_required']==0:break
        time.sleep(1)
    report['status_after']=status
    check('reconciliation_restored',status['reconciliation']['state']=='balanced' and status['reconciliation']['difference']=='0' and status['transfers']['counts']['intervention_required']==0,status['reconciliation'])
    report['passed']=True
finally:
    report.update(ended_utc=b.utc(),commands=b.RECORDS)
    b.write_json(folder/'recovery.json',report)
    print(json.dumps({'recovery_passed':report['passed'],'checks':len(report['checks']),'report':str(folder/'recovery.json')}))
