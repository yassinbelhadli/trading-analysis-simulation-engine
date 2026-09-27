"""Search widget HTML/JS for volume-related settings and params."""
import requests, re

url = ('https://s.tradingview.com/widgetembed/'
       '?symbol=OANDA:XAUUSD&interval=5'
       '&hidesidetoolbar=1&theme=light&style=1'
       '&timezone=Etc/UTC&withfooter=0&hideideas=1&noStudies=true')

r = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
html = r.text

# Find widgetDefaults content
for m in re.finditer(r'widgetDefaults[^}]*\{', html):
    i = m.start()
    snippet = html[i:i+1500]
    print("=== widgetDefaults context ===")
    print(snippet[:1200])
    print()
    break

# Search for volume-related keywords
for kw in ['volume', 'Volume', 'VOL', 'hide_vol', 'vol_' ]:
    count = html.count(kw)
    if count:
        print(f"'{kw}': {count} occurrences")
        i = html.find(kw)
        print(f"  first at {i}: ...{html[max(0,i-80):i+150]}...")
        print()
