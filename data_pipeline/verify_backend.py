"""Acceptance of generated gold against unmodified backend, isolated in-memory ops DB."""
from __future__ import annotations
import argparse
import json
import logging
import os
from pathlib import Path
import sys

from .lineage import write_json
from .source import ROOT


def verify(gold: Path, scenarios: Path, policy: Path):
    # This command runs in a separate process. It cannot reset the user's ops.sqlite.
    os.environ.update(OPS_DB_PATH=':memory:',GOLD_DB_PATH=str(gold.resolve()),
                      POLICY_PATH=str(policy.resolve()),DEMO_OTP='123456',
                      JWT_SECRET='pipeline-acceptance-only-not-a-production-secret',FAULT_INJECTION='false')
    sys.path.insert(0,str(ROOT/'backend'))
    from fastapi.testclient import TestClient
    from app.main import app
    from app.store import reset_store, store
    from app.tools import data_source
    logging.getLogger('latam.trace').disabled=True
    client=TestClient(app)
    results=[]
    assert client.get('/api/health').json()['data_manifest']=='gold:'+gold.name
    for scenario in json.loads(scenarios.read_text(encoding='utf-8')):
        reset_store()
        result={'scenario':scenario['scenario'],'passed':False}
        try:
            login=client.post('/api/auth/login',json={'customer_id':scenario['customer_id'],'otp':'123456'})
            assert login.status_code==200, 'login'
            headers={'Authorization':'Bearer '+login.json()['access_token']}
            def chat(body):
                response=client.post('/api/chat',headers=headers,json=body)
                assert response.status_code==200,'chat HTTP'
                return response.json()
            body=chat({'message':scenario['message']})
            if scenario['scenario']=='ambiguous':
                assert body['ui'] and body['ui']['type']=='transaction_options','expected ambiguity'
                assert len(body['ui']['options'])>=2,'multiple candidates'
            if scenario['scenario'] in ('normal','portuguese'):
                assert body['ui'] and body['ui']['type']=='confirmation','expected unique normal candidate'
            if body['ui'] and body['ui']['type']=='transaction_options':
                assert scenario['transaction_id'] in [x['transaction_id'] for x in body['ui']['options']], 'target not in displayed candidates'
                body=chat({'conversation_id':body['conversation_id'],'ui_action':{
                    'type':'select_transaction','transaction_id':scenario['transaction_id']}})
            rule=body['audit']['rule_id']
            if scenario['expected_rule']:
                assert rule==scenario['expected_rule'],'unexpected policy rule'
            for _ in range(3):
                ui=body['ui']
                if not ui or ui['type']!='confirmation':
                    break
                body=chat({'conversation_id':body['conversation_id'],'ui_action':{
                    'type':'confirm','pending_action_id':ui['pending_action']['pending_action_id']}})
            if rule=='R12':
                assert body['case'] and body['case']['transaction_id']==scenario['transaction_id'],'case target'
                assert not body['handoff_id'],'normal case escalated'
            elif rule in ('R7','R8','R9','R10'):
                assert body['state']=='HANDOFF' and body['handoff_id'],'missing handoff'
                assert body['case'] and body['case']['transaction_id']==scenario['transaction_id'],'handoff case target'
                if rule=='R7':
                    assert store.card_blocks[scenario['product_id']].status=='Blocked','missing block'
            elif rule=='R2':
                assert not store.cases,'declined transaction created a case'
            if scenario['language']=='pt':
                assert body['language']=='pt','Portuguese lost'
            result.update(passed=True,rule=rule,final_state=body['state'])
        except AssertionError as exc:
            result['failure']=str(exc)  # only our fixed assertions, no backend payloads
        results.append(result)
    data_source.reset_connection()
    return {'passed':bool(results) and all(x['passed'] for x in results),'scenarios':results,
            'scope':'Real gold, current NLU, HTTP login/search/selection/confirmation/case/handoff; SQLite in memory.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gold',type=Path,default=ROOT/'data/gold/gold.duckdb')
    parser.add_argument('--scenarios',type=Path,default=ROOT/'reports/demo_scenarios.json')
    parser.add_argument('--policy',type=Path,default=ROOT/'config/policy.yaml')
    parser.add_argument('--report',type=Path,default=ROOT/'reports/backend_acceptance.json')
    args=parser.parse_args()
    try:
        report=verify(args.gold,args.scenarios,args.policy)
    except Exception as exc:
        report={'passed':False,'error_type':type(exc).__name__}
    write_json(args.report,report)
    print(json.dumps(report,ensure_ascii=True))
    raise SystemExit(0 if report['passed'] else 1)


if __name__=='__main__':
    main()
