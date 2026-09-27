"""Fetch widgetembed HTML and inspect initData/chartConfig structure."""
import requests, re

url = ('https://s.tradingview.com/widgetembed/'
       '?symbol=OANDA:XAUUSD&interval=5'
       '&hidesidetoolbar=1&theme=light&style=1'
       '&timezone=Etc/UTC&withfooter=0&hideideas=1&noStudies=true')

r = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
html = r.text
print(f"HTML length: {len(html)}")

# Find initData script
for m in re.finditer(r'<script>(.*?)</script>', html, re.DOTALL):
    body = m.group(1)
    if 'initData' in body:
        print("=== initData script found ===")
        print(body[:3000])
        print("...")
        break

# Look for "overrides" or "candleStyle" or "chartConfig" anywhere
for kw in ['overrides', 'candleStyle', 'chartConfig', 'initData', 'widgetConfig']:
    idxs = [i for i in range(len(html)) if html.startswith(kw, i)]
    print(f"\n'{kw}' occurrences: {len(idxs)}")
    if idxs:
        i = idxs[0]
        print(f"  context: ...{html[max(0,i-100):i+200]}...")
