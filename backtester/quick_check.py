import sys; sys.path.insert(0, '.')
from backtester.validate_ict_pipeline import run_symbol, compute_stats

all_sigs = []
for sym in ['BTCUSD', 'ETHUSD']:
    sigs = run_symbol(sym, '1h', 1500)
    all_sigs.extend(sigs)
    print(f"{sym}: {len(sigs)} signals")

stats = compute_stats(all_sigs, '1h_combined')
print(f"Total: {stats['total_entries']} entries, {stats['win_rate_pct']:.1f}% WR, {stats['expectancy']:.3f}R")
