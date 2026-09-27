"""BOS validation report — scored classification with new 0-100 scale."""
import sys, os; sys.path.insert(0,'.')
os.environ['PYTHONIOENCODING'] = 'utf-8'
import logging; logging.basicConfig(level=logging.WARNING, force=True)
from datetime import datetime

from data.kline_loader import fetch_klines
from detection.swing import detect_swings, classify_swings
from detection.structure import detect_bos
from detection.bos_scorer import classify_bos

OUT = open("bos_validation_report.txt", "w", encoding="utf-8")

def log(msg=""):
    OUT.write(msg + "\n"); OUT.flush()

def ts(t):
    return datetime.utcfromtimestamp(t).strftime("%Y-%m-%d %H:%M")

def run(label, symbol, interval, limit=400):
    log(f"\n{'='*90}")
    log(f"BOS VALIDATION: {label}")
    log(f"{'='*90}")

    candles = fetch_klines(symbol, interval, limit)
    if not candles:
        log("  FAILED: no data"); return

    log(f"  Data: {len(candles)} candles ({interval}) | "
        f"{ts(candles[0]['time'])} → {ts(candles[-1]['time'])}")

    raw = detect_swings(candles)
    swings = classify_swings(raw)
    classified = [s for s in swings if s["type"] in ("HH","LH","HL","LL")]

    bos_list = detect_bos(classified, candles)
    bos_list = classify_bos(bos_list, classified, candles)

    log(f"\n  Total BOS: {len(bos_list)}")

    strong = [b for b in bos_list if b["classification"] == "Strong BOS"]
    good = [b for b in bos_list if b["classification"] == "Good BOS"]
    weak = [b for b in bos_list if b["classification"] == "Weak BOS"]
    ignore = [b for b in bos_list if b["classification"] == "Ignore"]
    ext = [b for b in bos_list if b.get("bos_type") == "External"]

    log(f"  ┌─────────────────────┬────────┐")
    log(f"  │ Strong BOS (80-100) │ {len(strong):4d}     │")
    log(f"  │ Good BOS (60-79)    │ {len(good):4d}     │")
    log(f"  │ Weak BOS (40-59)    │ {len(weak):4d}     │")
    log(f"  │ Ignore (0-39)       │ {len(ignore):4d}     │")
    log(f"  │ External            │ {len(ext):4d}     │")
    log(f"  │ Internal            │ {len(bos_list)-len(ext):4d}     │")
    log(f"  └─────────────────────┴────────┘")

    log(f"\n  {'='*90}")
    log(f"  DETAILED BOS LIST (sorted by score descending)")
    log(f"  {'='*90}\n")

    sorted_bos = sorted(bos_list, key=lambda b: b.get("score", 0), reverse=True)

    hdr = (f"  {'#':>3s} {'Dir':6s} {'Score':>5s} {'Class':11s} {'Type':9s} "
           f"{'Swing#':>6s} {'Break#':>6s} {'Swing $':>8s} {'Close $':>8s} "
           f"{'Disp%':>7s} {'Dist':>4s} {'SwingType':>5s} {'Time'}")
    log(hdr)
    log(f"  {'-'*len(hdr)}")

    for i, b in enumerate(sorted_bos):
        s_idx = b.get("swing_index", 0)
        b_idx = b["candle_index"]
        close_price = None
        for c in candles:
            if c["index"] == b_idx:
                close_price = c["close"]; break
        log((f"  {i+1:3d} {b['direction']:6s} "
             f"{b.get('score',0):5d} {b.get('classification','?'):11s} {b.get('bos_type','?'):9s} "
             f"{s_idx:6d} {b_idx:6d} "
             f"{b['price']:>8.2f} "
             f"{close_price:>8.2f} "
             f"{b.get('displacement_pct',0):>7.3f}% "
             f"{b_idx - s_idx:4d} "
             f"{b.get('swing_type','?'):>5s} "
             f"{ts(candles[b_idx]['time']):>16s}"))

    log(f"\n  {'='*90}")
    log(f"  SCORING BREAKDOWN")
    log(f"  {'='*90}\n")

    for i, b in enumerate(sorted_bos):
        bd = b.get("breakdown", {})
        log((f"  [{i+1:2d}] Score={b.get('score',0):3d} | "
             f"C1={bd.get('close_beyond',0):2d} "
             f"C2={bd.get('body_beyond',0):2d} "
             f"C3={bd.get('strong_candle',0):2d} "
             f"C4={bd.get('displacement',0):2d} "
             f"C5={bd.get('structure',0):2d} "
             f"C6={bd.get('atr_expansion',0):2d} "
             f"C7={bd.get('bos_distance',0):2d} "
             f"C8={bd.get('volume',0):2d} | "
             f"{b['direction']:7s} {b.get('classification','?'):11s} "
             f"{b.get('bos_type','?'):8s} "
             f"@candle={b['candle_index']} {b.get('displacement_pct',0):.3f}%"))

    score_vals = [b.get("score",0) for b in bos_list]
    avg_score = sum(score_vals)/len(score_vals) if score_vals else 0
    log(f"\n  Average score: {avg_score:.1f}  |  "
        f"Strong={len(strong)}  Good={len(good)}  Weak={len(weak)}  Ignore={len(ignore)}")

    # Top 20 for screenshot validation
    top20 = sorted_bos[:20]
    log(f"\n  {'='*90}")
    log(f"  TOP 20 BOS (candidates for screenshot validation)")
    log(f"  {'='*90}\n")
    log(f"  {'#':>3s} {'Score':>5s} {'Dir':6s} {'Class':11s} {'Type':9s} "
        f"{'Break#':>6s} {'Time'}")
    log(f"  {'-'*55}")
    for i, b in enumerate(top20):
        log((f"  {i+1:3d} {b.get('score',0):5d} {b['direction']:6s} "
             f"{b.get('classification','?'):11s} {b.get('bos_type','?'):9s} "
             f"{b['candle_index']:6d} {ts(candles[b['candle_index']]['time']):>16s}"))

run("BTCUSD 15m (400 candles)", "BTCUSD", "15m", 400)
run("BTCUSD 30m (300 candles)", "BTCUSD", "30m", 300)
run("ETHUSD 15m (400 candles)", "ETHUSD", "15m", 400)

OUT.close()
print("Written to bos_validation_report.txt")
