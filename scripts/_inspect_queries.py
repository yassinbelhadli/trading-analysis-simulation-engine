"""Inspect how querySettings is built from URL params."""
import requests, re

url = ('https://s.tradingview.com/widgetembed/'
       '?symbol=OANDA:XAUUSD&interval=5'
       '&hidesidetoolbar=1&theme=light&style=1'
       '&timezone=Etc/UTC&withfooter=0&hideideas=1&noStudies=true')

r = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
html = r.text

# Find all occurrences of querySettings
for m in re.finditer(r'querySettings', html):
    i = m.start()
    print(f"--- context around {i} ---")
    print(html[max(0,i-300):i+300])
    print()
    if i > 3000:
        break
