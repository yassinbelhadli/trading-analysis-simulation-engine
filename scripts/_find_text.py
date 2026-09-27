"""Analyze all visible elements on the widget page."""
import requests, re

url = 'https://s.tradingview.com/widgetembed/?symbol=OANDA:XAUUSD&interval=5&hidesidetoolbar=1&theme=light&style=1&timezone=Etc/UTC&withfooter=0&hideideas=1&noStudies=true'
r = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})

# Extract all text content
texts = re.findall(r'>([^<]{2,100})<', r.text)
for t in texts:
    t = t.strip()
    if t:
        print(f'  {repr(t)}')
