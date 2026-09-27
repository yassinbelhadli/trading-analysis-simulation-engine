# ICT / SMC RULES SPECIFICATION (ENGINE VERSION 1.0)

This document defines the exact deterministic rules used by the trading engine.

All modules (Market Structure, Liquidity, FVG, Scoring) MUST strictly follow these rules.

No deviation is allowed in implementation.

---

# 1. SWING STRUCTURE

## Swing High

A Swing High is confirmed when:

- High[i] is greater than the highs of N candles on both sides
- Default N = 3

Formula:
High[i] > High[i-k] AND High[i] > High[i+k] for k = 1..N

---

## Swing Low

A Swing Low is confirmed when:

- Low[i] is lower than the lows of N candles on both sides
- Default N = 3

---

# 2. BOS (BREAK OF STRUCTURE)

## Bullish BOS

A Bullish BOS occurs when:

- Candle Close breaks ABOVE the previous confirmed Swing High

Condition:
Close[i] > SwingHigh[last]

AND

- No requirement of trend reversal

---

## Bearish BOS

Occurs when:

- Close breaks BELOW previous Swing Low

Condition:
Close[i] < SwingLow[last]

---

# 3. CHoCH (CHANGE OF CHARACTER)

## Bullish CHoCH

Occurs when:

- Market is in bearish trend
- Close breaks ABOVE last Swing High

Condition:
Trend = Bearish AND Close > SwingHigh

---

## Bearish CHoCH

Occurs when:

- Market is in bullish trend
- Close breaks BELOW last Swing Low

Condition:
Trend = Bullish AND Close < SwingLow

---

# 4. MSS (MOMENTUM SHIFT STRUCTURE)

MSS is a refinement of CHoCH.

## Bullish MSS

Occurs when:

1. Liquidity is taken below a Swing Low (sweep)
2. Price then closes above the last Swing High

Sequence:
Sweep Low → Displacement Up → Break Structure

---

## Bearish MSS

Occurs when:

1. Liquidity is taken above a Swing High (sweep)
2. Price then closes below the last Swing Low

Sequence:
Sweep High → Displacement Down → Break Structure

---

# 5. LIQUIDITY SWEEP

## Bullish Liquidity Sweep (Buy-side grab)

Occurs when:

- High[i] takes a known liquidity level (EQH / PDH / Asian High)
- AND Close[i] closes BELOW that level

Condition:
High[i] > Liquidity_Level
AND Close[i] < Liquidity_Level

---

## Bearish Liquidity Sweep (Sell-side grab)

Occurs when:

- Low[i] takes liquidity level (EQL / PDL / Asian Low)
- AND Close[i] closes ABOVE that level

Condition:
Low[i] < Liquidity_Level
AND Close[i] > Liquidity_Level

---

# 6. FAIR VALUE GAP (FVG)

FVG is a 3-candle imbalance.

Let:

- Candle 1 = i-2
- Candle 2 = i-1
- Candle 3 = i

---

## Bullish FVG

Occurs when:

High[i-2] < Low[i]

Zone:
- Lower = High[i-2]
- Upper = Low[i]

---

## Bearish FVG

Occurs when:

Low[i-2] > High[i]

Zone:
- Lower = High[i]
- Upper = Low[i-2]

---

# 7. ORDER BLOCK (OB)

## Bullish OB

Last bearish candle before bullish displacement.

Conditions:

- Bearish candle followed by strong bullish displacement
- Break of structure upward after candle

---

## Bearish OB

Last bullish candle before bearish displacement.

Conditions:

- Bullish candle followed by strong bearish displacement
- Break of structure downward after candle

---

# 8. DISPLACEMENT

A displacement candle is valid when:

- Candle body > ATR * multiplier (default 1.2)
- Strong directional close

Bullish:
Close > Open AND body expansion

Bearish:
Close < Open AND body expansion

---

# 9. GENERAL RULES

## Rule 1: No Lookahead Bias
- Only past and current candles allowed
- No future data used in detection

## Rule 2: Confirmation Delay
- Swings must be confirmed using past N candles

## Rule 3: Zone Persistence
- Liquidity zones remain active until mitigated

## Rule 4: No Repainting
- Once structure or FVG is detected, it cannot change

---

# 10. ENGINE PRIORITY ORDER

When conflicts occur:

1. Liquidity Sweep (highest priority)
2. MSS / CHoCH
3. BOS
4. FVG
5. OB
6. Candle confirmation

---

END OF SPECIFICATION