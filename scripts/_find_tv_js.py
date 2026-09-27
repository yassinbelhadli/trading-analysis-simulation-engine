"""Find the correct TV widget script URL."""
import requests, re

url = 'https://s.tradingview.com/widgetembed/?symbol=OANDA:XAUUSD&interval=5'
r = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})

for m in re.finditer(r'<script[^>]*src="([^"]+)"', r.text):
    src = m.group(1)
    if 'tv' in src.lower() or 'widget' in src.lower() or 'chart' in src.lower():
        print(f'Script: {src}')

# Check inline TradingView calls
for m in re.finditer(r'<script>(.*?)</script>', r.text, re.DOTALL):
    if 'TradingView' in m.group(1):
        print(f'Inline: {m.group(1)[:200]}')
