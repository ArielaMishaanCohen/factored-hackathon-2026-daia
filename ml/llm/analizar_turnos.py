"""Resume las corridas de medir_turnos.py (Paso 11). Uso: python ml/llm/analizar_turnos.py ml/llm/runs"""
import json, sys, statistics as st, collections as C
import numpy as np
S=sys.argv[1]
def p(xs,q): return float(np.percentile(xs,q)) if xs else float('nan')
for modo in ("20260930-paso11_sin", "20260930-paso11_gemini"):
    r=json.load(open(f"{S}/{modo}.json"))
    print("=====",modo, "turnos",len(r))
    for t in r:
        t["api"]=[l for l in t["llamadas"] if not l.get("error") and not l.get("cached")]
    # frío
    print("primer turno (frío):", round(r[0]["ms"]))
    cal=r[1:]
    ms=[t["ms"] for t in cal]
    print("TODOS los turnos sin frío: p50 %.0f p95 %.0f max %.0f"%(p(ms,50),p(ms,95),max(ms)))
    ms2=[t["ms"] for t in r]; print("  con frío p50 %.0f p95 %.0f"%(p(ms2,50),p(ms2,95)))
    # por tipo de entrada
    for k in ("message","select_transaction","confirm"):
        x=[t["ms"] for t in cal if t["entrada"]==k]
        if x: print(f"  entrada {k}: n={len(x)} p50 %.0f p95 %.0f max %.0f"%(p(x,50),p(x,95),max(x)))
    print("por escenario/turno: n, p50, p95, max ms, llamadas api/turno, tipos, tokens in/out medio, usd medio, sources")
    g=C.defaultdict(list)
    for t in r: g[(t["escenario"],t["turno"],t["entrada"],t["estado"])].append(t)
    for k,ts in g.items():
        x=[t["ms"] for t in ts if t is not r[0]]
        tipos=C.Counter(l["tipo"] for t in ts for l in t["api"])
        print(" ",k, len(ts),"%.0f %.0f %.0f"%(p(x,50),p(x,95),max(x)), sum(len(t["api"]) for t in ts)/len(ts), dict(tipos),
              round(st.mean(sum(l["tin"] for l in t["api"]) for t in ts)), round(st.mean(sum(l["tout"] for l in t["api"]) for t in ts)),
              "%.5f"%st.mean(sum(l["usd"] for l in t["api"]) for t in ts), C.Counter(s for t in ts for s in t["sources"]))
    print("por conversación")
    conv=C.defaultdict(list)
    for t in r: conv[(t["rep"],t["escenario"])].append(t)
    ce=C.defaultdict(list)
    for (rep,e),ts in conv.items():
        ce[e].append(dict(ms=sum(t["ms"] for t in ts),n=len(ts),api=sum(len(t["api"]) for t in ts),
            tin=sum(l["tin"] for t in ts for l in t["api"]),tout=sum(l["tout"] for t in ts for l in t["api"]),
            usd=sum(l["usd"] for t in ts for l in t["api"]), cached=sum(1 for t in ts for l in t["llamadas"] if l.get("cached")),
            err=sum(1 for t in ts for l in t["llamadas"] if l.get("error"))))
    allc=[c for v in ce.values() for c in v]
    for e,v in ce.items():
        print("  %-14s turnos %d  ms p50 %.0f max %.0f  api %.1f  tin %.0f tout %.0f usd %.5f cached %.1f err %.1f"%(e,v[0]["n"],p([c["ms"] for c in v],50),max(c["ms"] for c in v),
              st.mean(c["api"] for c in v),st.mean(c["tin"] for c in v),st.mean(c["tout"] for c in v),st.mean(c["usd"] for c in v),st.mean(c["cached"] for c in v),st.mean(c["err"] for c in v)))
    print("  TODAS: conv ms p50 %.0f p95 %.0f; api/conv %.2f; usd/conv medio %.5f; usd 5 escenarios %.5f"%(p([c["ms"] for c in allc],50),p([c["ms"] for c in allc],95),
          st.mean(c["api"] for c in allc), st.mean(c["usd"] for c in allc), sum(c["usd"] for c in allc)/5))
    api=[l for t in r for l in t["api"]]
    if api:
        for tipo in sorted({l["tipo"] for l in api}):
            x=[l["ms"] for l in api if l["tipo"]==tipo]
            print(f"  llamada {tipo}: n={len(x)} p50 %.0f p95 %.0f max %.0f  tin medio %.0f tout medio %.0f"%(p(x,50),p(x,95),max(x),st.mean(l["tin"] for l in api if l["tipo"]==tipo),st.mean(l["tout"] for l in api if l["tipo"]==tipo)))
    lentos=[t for t in r if t["ms"]>8000]
    print("  turnos >8s:",len(lentos))
    for t in lentos: print("   ",t["rep"],t["escenario"],t["turno"],round(t["ms"]),[ (l["tipo"],round(l["ms"])) for l in t["llamadas"]],[(s["n"],s["ms"]) for s in t["spans"]])
    print("  turnos >5s:",[(t["rep"],t["escenario"],t["turno"],round(t["ms"])) for t in r if t["ms"]>5000])
