"""Historical denominators and temporal calibration; holdout never selects thresholds."""
from .lineage import write_json


def rows(con, sql, params=None):
    result = con.execute(sql, params or [])
    columns = [d[0] for d in result.description]
    return [dict(zip(columns, row)) for row in result.fetchall()]


def analyze(con, run_dir, policy):
    periods = {'calibration': ('2025-07-01','2026-03-31'), 'test': ('2026-04-01',policy['reference_date'])}
    fraud = {}
    for split,(lo,hi) in periods.items():
        population = con.execute('SELECT count(*), count(*) FILTER(WHERE is_fraud), '
                                 'count(*) FILTER(WHERE fraud_score IS NULL) FROM transactions '
                                 'WHERE business_date BETWEEN ? AND ?', [lo,hi]).fetchone()
        thresholds = []
        for threshold in range(101):
            predicted,tp = con.execute('SELECT count(*),count(*) FILTER(WHERE is_fraud) '
                'FROM transactions WHERE business_date BETWEEN ? AND ? AND fraud_score >= ?',
                [lo,hi,threshold]).fetchone()
            thresholds.append({'threshold':threshold,'tp':tp,'predicted':predicted,
                               'precision':tp/predicted if predicted else None,
                               'recall_all_fraud':tp/population[1] if population[1] else None})
        fraud[split] = {'from':lo,'to':hi,'n':population[0],'fraud_n':population[1],
                         'null_score_n':population[2], 'thresholds':thresholds}
    proposal = {}
    for name, target in [('fraud_score_low',.30),('fraud_score_high',.99)]:
        candidates = [r for r in fraud['calibration']['thresholds']
                      if r['predicted']>=20 and r['precision'] is not None and r['precision']>=target]
        proposal[name] = min((r['threshold'] for r in candidates), default=None)
    amount = rows(con,"""SELECT transaction_type,count(*) n,
        quantile_cont(amount_usd,.90) p90,quantile_cont(amount_usd,.95) p95
        FROM transactions WHERE business_date BETWEEN DATE '2025-07-01' AND DATE '2026-03-31'
        GROUP BY transaction_type ORDER BY transaction_type""")
    proposal['amount_usd_max'] = {r['transaction_type']:round(r['p95'],2) for r in amount}
    amount_test = rows(con,"""SELECT transaction_type,count(*) n,
        quantile_cont(amount_usd,.90) p90,quantile_cont(amount_usd,.95) p95
        FROM transactions WHERE business_date BETWEEN DATE '2026-04-01' AND ?
        GROUP BY transaction_type ORDER BY transaction_type""", [policy['reference_date']])
    report = {'method':'Lowest integer score with calibration precision >= target and >=20 predictions; test is evaluation only.',
              'targets':{'low_precision':.30,'high_precision':.99,'minimum_predictions':20},
              'fraud':fraud,'amount_calibration':amount,'amount_test':amount_test,'proposal':proposal,
              'current_policy_version':policy['policy_version'],
              'claim_window_days':{'value':policy['rules']['claim_window_days'],
                                   'basis':'Synthetic business policy; not statistically identifiable from these data.'},
              'limitations':['Synthetic dataset; no production performance claim.',
                             'Null scores stay unknown; recall denominator includes fraud with missing scores.',
                             'Fraud-score calibration is not end-to-end policy evaluation.']}
    report['adopted'] = {
        'fraud_score_low':policy['rules']['fraud_score_low'],
        'fraud_score_high':policy['rules']['fraud_score_high'],
        'amount_usd_max':policy['rules']['amount_usd_max'],
        'rationale':'Retain agreed conservative fraud bands 30/40; empirical alternative 31 requires coordination with backend (fixed score=35 R9 test). Amount thresholds use calibration p95.'}
    report['adopted_fraud_evaluation'] = {
        split:{name:next(r for r in fraud[split]['thresholds'] if r['threshold']==policy['rules'][name])
               for name in ('fraud_score_low','fraud_score_high')}
        for split in periods}
    metrics = {'scope':'Historical data through reference date; transactions only July 2025 through reference date.',
               'reference_date':policy['reference_date'],
               'call_center_by_category': rows(con,"""SELECT reason_category,count(*) contacts,
                    count(was_resolved) fcr_denominator,
                    count(*) FILTER(WHERE was_resolved) fcr_numerator,
                    avg(CAST(was_resolved AS INT)) fcr,
                    count(*) FILTER(WHERE was_resolved=false) unresolved,
                    avg(duration_seconds) mean_duration_seconds,
                    count(duration_seconds) duration_denominator
                    FROM call_center_interactions GROUP BY reason_category ORDER BY reason_category"""),
               'complaints':rows(con,"""SELECT count(*) total,count(subcategory) labeled,
                    count(*) FILTER(WHERE subcategory IN ('Cargo no reconocido','Cobro indebido')) disputes
                    FROM complaints""")[0],
               'disputes':rows(con,"""SELECT count(*) n,avg(resolution_days) mean_resolution_days,
                    median(resolution_days) median_resolution_days,count(resolution_days) resolution_denominator,
                    count(*) FILTER(WHERE sla_breached) sla_breached_numerator,
                    count(sla_breached) sla_denominator,
                    count(*) FILTER(WHERE status IN ('Open','In Process')) open_or_in_process
                    FROM complaints WHERE subcategory IN ('Cargo no reconocido','Cobro indebido')""")[0],
               'csat_by_contact_reason':rows(con,"""SELECT i.reason_category,count(*) n,
                    avg(s.main_score) mean_csat FROM satisfaction_surveys s
                    JOIN call_center_interactions i USING(interaction_id)
                    WHERE s.survey_type='CSAT' GROUP BY i.reason_category ORDER BY i.reason_category"""),
               'transactions_by_currency':rows(con,"""SELECT currency,count(*) n,
                    count(*) FILTER(WHERE fraud_score IS NULL) null_score_n,median(amount_usd) median_amount_usd
                    FROM transactions GROUP BY currency ORDER BY currency"""),
               'limitations':['All complaints and labeled complaints have different denominators.',
                              'CSAT only; do not average CSAT, NPS and CES together.',
                              'Historical baseline is not the held-out conversation workload.']}
    metrics['populations'] = {
        table:rows(con,f'SELECT count(*) n,min(business_date) date_from,max(business_date) date_to FROM {table}')[0]
        for table in ('transactions','complaints','call_center_interactions','satisfaction_surveys')}
    write_json(run_dir/'policy_calibration.json',report)
    write_json(run_dir/'metricas_problema.json',metrics)
    import json
    con.execute('CREATE TABLE baseline_metrics (metric VARCHAR PRIMARY KEY, value_json VARCHAR NOT NULL)')
    con.executemany('INSERT INTO baseline_metrics VALUES (?,?)',
                    [(k,json.dumps(v,ensure_ascii=False,default=str)) for k,v in metrics.items()])
    return report, metrics
