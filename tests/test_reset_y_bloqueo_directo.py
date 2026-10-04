"""Regresiones: reinicio aislado y bloqueo sin asumir cargos fraudulentos."""
from dataclasses import replace
from datetime import datetime, timezone

from app import main, orchestrator
from app.config import Settings
from app.schemas import CardStatus, NLUResult
from app.store import store, simulate_restart
from app.tools import data_source


def chat(client, headers, **body):
    r = client.post('/api/chat', headers=headers, json=body)
    assert r.status_code == 200, r.text
    return r.json()


def stolen(monkeypatch):
    monkeypatch.setattr(orchestrator, 'understand_con_uso', lambda *a, **kw: (
        NLUResult(language='es', intent='tarjeta_comprometida', intent_confidence=.99,
                  abstain=False, extractor='rules', model_version='test'), None))


def confirm(client, headers, r, action='confirm'):
    return chat(client, headers, conversation_id=r['conversation_id'], ui_action={
        'type': action, 'pending_action_id': r['ui']['pending_action']['pending_action_id']})


def test_empty_secret(monkeypatch):
    monkeypatch.setenv('JWT_SECRET', '')
    assert Settings().jwt_secret
    monkeypatch.setenv('JWT_SECRET', 'provided-secret')
    assert Settings().jwt_secret == 'provided-secret'


def test_stolen_no_charge_blocks_only(client, auth, monkeypatch):
    stolen(monkeypatch)
    h = auth()
    r = chat(client, h, message='me robaron mi tarjeta la tengo que cancelar')
    assert r['ui']['pending_action']['action'] == 'block_card'
    assert 'search_transactions' not in str(r['audit']['tools'])
    assert not store.card_blocks and not store.cases
    r = confirm(client, h, r)
    assert store.card_blocks['PRD-DEMO-01'].status == 'Blocked'
    assert r['case'] is None and not store.cases
    assert 'Si también' in ' '.join(m['text'] for m in r['messages'])


def test_multiple_cards_asks_card_not_charge(client, auth, monkeypatch):
    stolen(monkeypatch)
    owned = data_source.customer_cards('CUS-DEMO-01')
    extra = {**owned[0], 'product_id': 'PRD-EXTRA', 'card_mask': '•••• 9999'}
    monkeypatch.setattr(data_source, 'customer_cards', lambda customer: owned + [extra])
    h = auth()
    r = chat(client, h, message='me robaron la tarjeta')
    assert r['state'] == 'ACLARAR' and r['ui'] is None
    r = chat(client, h, conversation_id=r['conversation_id'], message='la 4821')
    assert r['ui']['pending_action']['action'] == 'block_card'
    assert not store.cases and not store.card_blocks


def test_cancel_direct_block(client, auth, monkeypatch):
    stolen(monkeypatch)
    h = auth()
    r = confirm(client, h, chat(client, h, message='me robaron mi tarjeta'), 'cancel')
    assert not store.card_blocks and not store.cases
    assert r['state'] == 'HANDOFF'
    assert next(iter(store.handoffs.values())).suggested_queue == 'fraude'


def test_confirmation_cannot_move_between_conversations(client, auth, monkeypatch):
    stolen(monkeypatch)
    h = auth()
    first = chat(client, h, message='me robaron la tarjeta')
    second = chat(client, h, message='me robaron la tarjeta')
    r = chat(client, h, conversation_id=second['conversation_id'], ui_action={
        'type': 'confirm', 'pending_action_id': first['ui']['pending_action']['pending_action_id']})
    assert not store.card_blocks
    assert not store.pending_actions[first['ui']['pending_action']['pending_action_id']].used


def test_demo_reset_is_scoped_and_persistent(client, auth):
    h = auth()
    other = auth('CUS-DEMO-02')
    r = chat(client, h, ui_action={'type': 'select_transaction', 'transaction_id': 'TX-DEMO-0001'})
    confirm(client, h, r)
    foreign = chat(client, other, ui_action={'type': 'select_transaction', 'transaction_id': 'TX-DEMO-0003'})
    confirm(client, other, foreign)
    store.card_blocks['PRD-DEMO-01'] = CardStatus(product_id='PRD-DEMO-01', card_mask='•••• 4821',
                                               status='Blocked', blocked_at=datetime.now(timezone.utc))
    assert any(c.customer_id == 'CUS-DEMO-01' for c in store.cases.values())
    seq = dict(store._seq)
    assert client.post('/api/auth/demo/reset', headers=h).status_code == 204
    simulate_restart()
    assert all(c.customer_id != 'CUS-DEMO-01' for c in store.cases.values())
    assert any(c.customer_id == 'CUS-DEMO-02' for c in store.cases.values())
    assert foreign['conversation_id'] in store.conversations
    assert r['conversation_id'] not in store.conversations
    assert 'PRD-DEMO-01' not in store.card_blocks
    assert store._seq == seq
    again = chat(client, h, ui_action={'type': 'select_transaction', 'transaction_id': 'TX-DEMO-0001'})
    assert again['audit']['rule_id'] != 'R5'


def test_reset_requires_auth_and_demo_mode(client, auth, monkeypatch):
    assert client.post('/api/auth/demo/reset').status_code == 401
    h = auth()
    monkeypatch.setattr(main, 'get_settings', lambda: replace(Settings(), demo_mode=False))
    assert client.post('/api/auth/demo/reset', headers=h).status_code == 404


def test_new_conversation_keeps_case(client, auth):
    h = auth('CUS-DEMO-02')
    r = chat(client, h, ui_action={'type': 'select_transaction', 'transaction_id': 'TX-DEMO-0003'})
    confirm(client, h, r)
    newer = chat(client, h, ui_action={'type': 'select_transaction', 'transaction_id': 'TX-DEMO-0003'})
    assert newer['conversation_id'] != r['conversation_id']
    assert newer['audit']['rule_id'] == 'R5'
