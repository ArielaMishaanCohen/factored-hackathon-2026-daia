"""Gold contract is read from the backend's specification without importing its code."""
import ast
from datetime import date, timedelta

from .source import ROOT
from .transform import literal

GOLD_TABLES = ('dispute_transactions', 'cards', 'customer_profile', 'demo_customers')


def backend_schema():
    tree = ast.parse((ROOT / 'scripts/make_demo_gold.py').read_text(encoding='utf-8'))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'SCHEMA' for t in node.targets):
            return ast.literal_eval(node.value)
    raise ValueError('No se encontró SCHEMA en la especificación del backend.')


def build_gold(con, run_dir, policy, quality, sample_customers=100, require_demos=True):
    con.execute(backend_schema())
    ref = date.fromisoformat(policy['reference_date'])
    rules = policy['rules']
    con.execute("""INSERT INTO dispute_transactions
        SELECT t.transaction_id,t.customer_id,t.product_id,t.business_date,t.amount,t.currency,
               t.amount_usd,t.merchant_name,t.transaction_type,t.channel,t.transaction_status,t.fraud_score
        FROM transactions t JOIN customers c USING(customer_id)
        JOIN products p ON p.product_id=t.product_id AND p.customer_id=t.customer_id""")
    discarded = con.execute('SELECT (SELECT count(*) FROM transactions)-(SELECT count(*) FROM dispute_transactions)').fetchone()[0]
    quality.check('gold.excluded_orphan_or_wrong_owner', discarded, severity='warning')
    con.execute("""INSERT INTO cards SELECT product_id, customer_id,
        CASE WHEN length(product_number)>=4 THEN '•••• ' || right(product_number,4) ELSE NULL END,
        product_status FROM products WHERE product_type IN ('Tarjeta Crédito','Tarjeta Débito')""")
    con.execute("""INSERT INTO customer_profile
        SELECT c.customer_id,c.segment,c.country, count(q.complaint_id)::INTEGER
        FROM customers c JOIN (SELECT DISTINCT customer_id FROM dispute_transactions) t USING(customer_id)
        LEFT JOIN complaints q ON q.customer_id=c.customer_id
          AND q.business_date BETWEEN ? AND ?
        GROUP BY c.customer_id,c.segment,c.country""", [ref-timedelta(days=rules['repeat_window_days']), ref])
    # All transaction types remain in full gold. Serving demo contains card transactions only:
    # do not invent a card for an account/loan product.
    limits = 'CASE t.transaction_type ' + ' '.join(
        f'WHEN {literal(k)} THEN {float(v)}' for k,v in rules['amount_usd_max'].items() if k != 'default') + f" ELSE {float(rules['amount_usd_max']['default'])} END"
    con.execute(f"""CREATE VIEW candidates AS SELECT t.*, c.status AS card_status,
        p.segment,p.country,p.prior_complaints_90d, {limits} AS amount_limit
        FROM dispute_transactions t JOIN cards c USING(product_id,customer_id)
        JOIN customer_profile p USING(customer_id)
        WHERE t.business_date BETWEEN DATE {literal(ref-timedelta(days=policy['search']['lookback_days']))}
          AND DATE {literal(ref)}""")
    low, high = float(rules['fraud_score_low']), float(rules['fraud_score_high'])
    recent = f"business_date >= DATE {literal(ref-timedelta(days=rules['claim_window_days']))}"
    safe = f"status='Approved' AND {recent}"
    normal = f"{safe} AND fraud_score < {low} AND amount_usd <= amount_limit AND prior_complaints_90d < {int(rules['repeat_disputes_k'])} AND merchant_name IS NOT NULL"
    tol = float(policy['search']['amount_tolerance_pct']) / 100
    unique = f"""AND (SELECT count(*) FROM candidates other WHERE other.customer_id=t.customer_id
        AND abs(other.amount-t.amount)<=t.amount*{tol}
        AND contains(lower(other.merchant_name),lower(t.merchant_name)))=1"""
    scenarios = [
        ('normal','Resolución normal',normal + ' ' + unique,'R12','es'),
        ('ambiguous','Ambiguo (varias candidatas)',f"{safe} AND EXISTS (SELECT 1 FROM candidates o WHERE o.customer_id=t.customer_id AND o.amount=t.amount AND o.transaction_id<>t.transaction_id)",None,'es'),
        ('fraud','Fraude con bloqueo y handoff',f"{safe} AND fraud_score >= {high} AND card_status='Active'",'R7','es'),
        ('gray','Zona gris',f"{safe} AND fraud_score >= {low} AND fraud_score < {high}",'R9','es'),
        ('unknown','Riesgo desconocido',f"{safe} AND fraud_score IS NULL",'R8','es'),
        ('high_amount','Monto alto',f"{safe} AND fraud_score < {low} AND amount_usd > amount_limit",'R10','es'),
        ('declined','Cargo rechazado',"status='Declined'",'R2','es'),
        ('portuguese','Português: resolução normal',normal + ' ' + unique,'R12','pt'),
    ]
    chosen, demos, missing = [], [], []
    for code, label, condition, rule, lang in scenarios:
        exclude = ' AND t.customer_id NOT IN (' + ','.join(literal(x) for x in chosen) + ')' if chosen else ''
        rel = con.execute('SELECT t.* FROM candidates t WHERE '+condition+exclude+' ORDER BY transaction_id LIMIT 1')
        row = rel.fetchone()
        if row is None:
            missing.append(code)
            continue
        item = dict(zip([d[0] for d in rel.description], row))
        chosen.append(item['customer_id'])
        con.execute('INSERT INTO demo_customers VALUES (?,?,?,?,?,?)',
                    [item['customer_id'],f'Cliente demo {len(chosen)}',item['segment'],item['country'],lang,label])
        # Decimal comma works with the current NLU stub; buttons avoid extractor limitations.
        amount = f"{item['amount']:.2f}".replace('.', ',')
        prompt = ('Não reconheço uma compra de ' if lang=='pt' else 'No reconozco un cargo de ') + amount
        if code in ('normal','portuguese'):
            prompt += (' em ' if lang=='pt' else ' en ') + item['merchant_name']
        demos.append({k:item[k] for k in ('customer_id','transaction_id','product_id','amount','currency','business_date','merchant_name')} |
                     {'scenario':code,'expected_rule':rule,'language':lang,'message':prompt,
                      'note':'Use transaction selection UI to test policy independently of the current NLU stub.'})
    required_missing = [x for x in missing if x in ('normal','ambiguous','fraud','portuguese')]
    quality.check('gold.required_demo_scenarios', len(required_missing),
                  severity='error' if require_demos else 'warning', details=required_missing)
    quality.check('gold.optional_demo_scenarios', len(missing)-len(required_missing), severity='warning', details=missing)
    con.execute(f"""CREATE TABLE serving_customers AS SELECT customer_id FROM demo_customers
        UNION SELECT customer_id FROM (SELECT DISTINCT customer_id FROM candidates
            ORDER BY md5(customer_id),customer_id LIMIT {int(sample_customers)})""")
    gold_dir = run_dir / 'gold'
    gold_dir.mkdir()
    for name, reduced in [('gold_full.duckdb',False),('gold.duckdb',True)]:
        path = gold_dir / name
        con.execute(f'ATTACH {literal(path)} AS output_db')
        con.execute(backend_schema().replace('CREATE TABLE ', 'CREATE TABLE output_db.'))
        for table in GOLD_TABLES:
            predicate = ''
            if reduced:
                predicate = ' WHERE customer_id IN (SELECT customer_id FROM serving_customers)'
                if table == 'dispute_transactions':
                    predicate += ' AND product_id IN (SELECT product_id FROM cards)'
            con.execute(f'INSERT INTO output_db.{table} SELECT * FROM {table}{predicate}')
        con.execute('CREATE TABLE output_db.baseline_metrics AS SELECT * FROM baseline_metrics')
        con.execute('DETACH output_db')
        quality.check(f'gold.{name}.exists', not path.exists())
    demo_path = gold_dir / 'gold.duckdb'
    quality.check('gold.demo_size_under_50MB', demo_path.stat().st_size >= 50*1024*1024)
    return demos, {'full_transactions':con.execute('SELECT count(*) FROM dispute_transactions').fetchone()[0],
                   'excluded_invalid_relationships': discarded, 'demo_customers':len(demos),
                   'demo_bytes':demo_path.stat().st_size}
