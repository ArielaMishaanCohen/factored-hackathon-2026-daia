"""Gráficas 3 y 4 para slides; usa resultados finales e histórico silver local."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import statistics
import zipfile

import duckdb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RUN = "20260929T234658Z-7cf922c1"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", type=Path, default=ROOT / "eval/reports/final_summary_datos.json")
    parser.add_argument("--silver", type=Path, default=ROOT / "data/runs" / RUN / "silver")
    parser.add_argument("--historical", type=Path, default=ROOT / "data/runs" / RUN / "metricas_problema.json")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/figures/datos")
    parser.add_argument("--green", default="#15803D")
    parser.add_argument("--amber", default="#D97706")
    parser.add_argument("--red", default="#DC2626")
    args = parser.parse_args()
    colors = [args.green, args.amber, args.red]
    if any(not re.fullmatch(r"#[0-9a-fA-F]{6}", x) for x in colors):
        parser.error("Los colores deben tener formato #RRGGBB")
    args.output.mkdir(parents=True, exist_ok=True)
    summary = json.loads(args.summary.read_text(encoding="utf8"))
    historical = json.loads(args.historical.read_text(encoding="utf8"))
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 14,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "svg.fonttype": "none", "axes.titleweight": "bold"})
    data = {"palette": dict(zip(["green", "amber", "red"], colors)), "palette_status": "provisional",
            "sources": {"summary": str(args.summary.relative_to(ROOT)) if args.summary.is_relative_to(ROOT) else str(args.summary),
                        "summary_sha256": hashlib.sha256(args.summary.read_bytes()).hexdigest(),
                        "silver": str(args.silver), "data_run": RUN}, "run_ids": [r["run_id"] for r in summary["runs"]]}

    def save(fig, name):
        fig.savefig(args.output / (name + ".png"), dpi=180, facecolor="white")
        fig.savefig(args.output / (name + ".svg"), facecolor="white")
        plt.close(fig)

    # 3. Language comparison: same cases, three repetitions, preserve denominators.
    systems = [("S", "with_gemini", "S + Gemini"), ("S", "without_gemini", "S sin Gemini"),
               ("B1", "without_gemini", "B1 reglas")]
    languages = [("es", "ES"), ("pt", "PT"), ("mix", "Mixto ES/PT")]
    metrics = [("safe_auto_resolution", "Resolución automática segura ↑"),
               ("case_correct", "Resultado correcto ↑"), ("missed_escalation", "Escalamiento faltante ↓")]
    fig, axes = plt.subplots(1, 3, figsize=(16, 8))
    fig.subplots_adjust(left=.13, right=.97, bottom=.23, top=.75, wspace=.24)
    fig.suptitle("Idiomas: desempeño y brechas en el held-out", x=.08, y=.95, ha="left", fontsize=24, weight="bold")
    fig.text(.08, .88, "Media y rango de 3 corridas finales · ES, PT y mixto; EN no fue evaluado", fontsize=15)
    parity = []
    for ax, (metric, title) in zip(axes, metrics):
        for j, (system, llm, label) in enumerate(systems):
            runs = [r for r in summary["runs"] if (r["system"], r["llm"]) == (system, llm)]
            assert len(runs) == 3
            for i, (lang, _) in enumerate(languages):
                ms = [next(m for m in r["metrics"] if m["name"] == metric and m["slice"] == {"language": lang}) for r in runs]
                assert len({m["denominator"] for m in ms}) == 1
                values = [m["value"] * 100 for m in ms]
                mean = statistics.mean(values)
                y = 2-i + (.18-j*.18)
                ax.plot([min(values), max(values)], [y, y], color=colors[j], lw=3)
                ax.scatter(mean, y, color=colors[j], s=65, marker=["o", "s", "D"][j], label=label if i == 0 else None, zorder=3)
                ax.annotate(f"{mean:.1f}%", (mean, y), xytext=(6, 0), textcoords="offset points", va="center", fontsize=11)
                parity.append(dict(metric=metric, language=lang, system=system, llm=llm,
                    mean_percent=mean, minimum_percent=min(values), maximum_percent=max(values),
                    denominators=[m["denominator"] for m in ms], numerators=[m["numerator"] for m in ms]))
        ns = [next(m["denominator"] for m in summary["runs"][0]["metrics"] if m["name"] == metric and m["slice"] == {"language": lang}) for lang, _ in languages]
        ax.set_yticks([2, 1, 0], [f"{label}\nn={int(n)}" for (_, label), n in zip(languages, ns)])
        ax.set_xlim(0, 105); ax.set_ylim(-.5, 2.5)
        ax.set_title(title, fontsize=14, pad=18)
        ax.set_xlabel("Porcentaje"); ax.grid(axis="x", alpha=.15)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", bbox_to_anchor=(.52, .12), ncol=3, frameon=False)
    fig.text(.08, .065, "Rango entre repeticiones ≠ intervalo de confianza. Las mezclas de casos difieren por idioma.", fontsize=12)
    data["parity"] = parity
    save(fig, "03_paridad_idioma")

    db = duckdb.connect()
    db.execute("SET TimeZone='UTC'")
    contacts = str(args.silver / "call_center_interactions.parquet")
    transactions = str(args.silver / "transactions.parquet")
    # 4a. Contact categories have no dispute-level label: do not manufacture one.
    reasons = db.execute("SELECT contact_reason, count(*) n FROM read_parquet(?) GROUP BY 1 ORDER BY n DESC", [contacts]).fetchall()
    assert sum(n for _, n in reasons) == historical["populations"]["call_center_interactions"]["n"]
    total = sum(n for _, n in reasons)
    cumulative = np.cumsum([n for _, n in reasons]) / total * 100
    fig, ax = plt.subplots(figsize=(16, 8)); fig.subplots_adjust(left=.08, right=.9, bottom=.25, top=.77)
    fig.suptitle("¿Por qué atender disputas? Contexto de contactos", x=.08, y=.95, ha="left", fontsize=23, weight="bold")
    fig.text(.08, .87, f"{total:,} contactos históricos · 2023-06-17 a 2026-06-17", fontsize=16)
    x = np.arange(len(reasons))
    bars = ax.bar(x, [n/1000 for _, n in reasons], color=[args.amber if name == "Queja" else args.green for name, _ in reasons], alpha=.9)
    ax.bar_label(bars, labels=[f"{n:,}" for _, n in reasons], padding=7, fontsize=13)
    ax.set_xticks(x, [name for name, _ in reasons]); ax.set_ylabel("Miles de contactos"); ax.set_ylim(0, max(n for _, n in reasons)/1000*1.2)
    second = ax.twinx(); second.plot(x, cumulative, color=args.red, marker="o", lw=2)
    second.set_ylim(0, 115); second.set_ylabel("Porcentaje acumulado")
    second.spines["top"].set_visible(False)
    fig.text(.08, .14, "Ámbar: Queja (117.021 contactos). La fuente no separa contactos por disputas dentro de Queja.", fontsize=13)
    fig.text(.08, .08, f"Evidencia complementaria: {historical['complaints']['disputes']:,} disputas en {historical['complaints']['total']:,} quejas; FCR de Queja 43,6 %.", fontsize=14, weight="bold")
    data["contact_pareto"] = [dict(reason=name, n=n, cumulative_percent=float(cum)) for (name, n), cum in zip(reasons, cumulative)]
    data["disputes_source"] = {"table": "complaints", "n": historical["complaints"]["disputes"], "total_complaints": historical["complaints"]["total"], "definition": ["Cargo no reconocido", "Cobro indebido"]}
    save(fig, "04a_pareto_contactos")

    # 4b. Convert the timestamp explicitly to UTC, not the machine time zone.
    heatrows = db.execute("""SELECT isodow(event_ts_utc AT TIME ZONE 'UTC')::INT weekday,
        hour(event_ts_utc AT TIME ZONE 'UTC')::INT hour_slot, count(*) n FROM read_parquet(?)
        WHERE event_ts_utc IS NOT NULL GROUP BY 1,2""", [contacts]).fetchall()
    heat = np.zeros((7, 24), dtype=int)
    for day, hour, n in heatrows: heat[day-1, hour] = n
    nulls = db.execute("SELECT count(*) FILTER(WHERE event_ts_utc IS NULL) FROM read_parquet(?)", [contacts]).fetchone()[0]
    assert int(heat.sum()) + nulls == total
    fig, ax = plt.subplots(figsize=(16, 8)); fig.subplots_adjust(left=.1, right=.92, bottom=.23, top=.76)
    fig.suptitle("Demanda histórica por día de semana y hora", x=.08, y=.95, ha="left", fontsize=24, weight="bold")
    fig.text(.08, .87, "Todos los contactos · volumen acumulado por franja UTC", fontsize=16)
    cmap = LinearSegmentedColormap.from_list("load", ["#F0FDF4", args.green, args.amber, args.red])
    im = ax.imshow(heat, cmap=cmap, aspect="auto", interpolation="nearest")
    ax.set_xticks(range(24), [f"{h:02}" for h in range(24)], fontsize=11)
    ax.set_yticks(range(7), ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"])
    ax.set_xlabel("Hora UTC"); fig.colorbar(im, ax=ax, pad=.02, label="Contactos acumulados")
    fig.text(.08, .12, f"n={int(heat.sum()):,}; timestamps ausentes={nulls}. No es una medida de saturación ni un promedio por día.", fontsize=13)
    fig.text(.08, .065, "Sin zona horaria declarada en el diccionario: timestamps sin offset asumidos UTC por el pipeline.", fontsize=12)
    data["demand_heatmap"] = {"timezone": "UTC", "aggregation": "historical counts", "counts": heat.tolist(), "n": int(heat.sum()), "null_timestamps": nulls}
    save(fig, "04b_demanda_hora_dia")

    # 4c. Outcome is the actual synthetic is_fraud label, not transaction_status.
    hist = db.execute("""SELECT is_fraud, least(floor(fraud_score/5)::INT,19) bin, count(*) n
        FROM read_parquet(?) WHERE fraud_score IS NOT NULL AND is_fraud IS NOT NULL GROUP BY 1,2""", [transactions]).fetchall()
    missing = db.execute("SELECT is_fraud, count(*) n, count(fraud_score) observed FROM read_parquet(?) GROUP BY 1", [transactions]).fetchall()
    counts = {False: np.zeros(20, dtype=int), True: np.zeros(20, dtype=int)}
    for outcome, bucket, n in hist: counts[outcome][bucket] = n
    assert sum(int(a.sum()) for a in counts.values()) == sum(observed for label, _, observed in missing if label is not None)
    fig, ax = plt.subplots(figsize=(16, 8)); fig.subplots_adjust(left=.09, right=.97, bottom=.22, top=.76)
    fig.suptitle("Fraud score por resultado real del dataset sintético", x=.08, y=.95, ha="left", fontsize=23, weight="bold")
    fig.text(.08, .87, "Transacciones jul-2025 a 17-jun-2026 · distribución normalizada dentro de cada grupo", fontsize=15)
    for outcome, color, label in [(False, args.green, "No fraude"), (True, args.red, "Fraude")]:
        n = int(counts[outcome].sum())
        ax.stairs(counts[outcome] / n * 100, np.arange(0, 101, 5), color=color, lw=3, label=f"{label} · score observado n={n:,}")
    ax.axvspan(30, 40, color=args.amber, alpha=.12)
    ax.axvline(30, color=args.amber, ls="--", lw=1.5)
    ax.axvline(40, color=args.red, ls="--", lw=1.5)
    ax.set_xlim(0, 100); ax.set_xlabel("Fraud score · umbrales de política 30 / 40")
    ax.set_ylabel("Porcentaje del grupo por intervalo de 5 puntos")
    ax.legend(frameon=False, fontsize=14); ax.grid(axis="y", alpha=.15)
    absent = sum(n-observed for _, n, observed in missing)
    population = sum(n for _, n, _ in missing)
    fig.text(.08, .12, f"Scores nulos: {absent:,}/{population:,} ({absent/population:.1%}); se excluyen de las curvas y permanecen como riesgo desconocido.", fontsize=13)
    fig.text(.08, .065, "Normalizar por grupo permite comparar formas; no representa la prevalencia de fraude ni una validación temporal.", fontsize=12)
    data["fraud_distribution"] = {"bins": list(range(0, 101, 5)), "counts": {str(k): v.tolist() for k, v in counts.items()},
        "populations": [dict(is_fraud=label, n=n, observed_score=observed) for label, n, observed in missing], "null_score_n": absent,
        "label": "is_fraud", "normalization": "within outcome group"}
    save(fig, "04c_fraud_score_resultado")
    db.close()
    (args.output / "datos_graficas.json").write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf8")
    with zipfile.ZipFile(args.output / "graficas_datos_slides.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for p in sorted(args.output.iterdir()):
            if p.suffix in (".png", ".svg", ".json", ".md"):
                archive.write(p, p.name)
    print(f"Gráficas y datos: {args.output}")


if __name__ == "__main__":
    main()
