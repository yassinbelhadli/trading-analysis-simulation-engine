"""Find where auto-trading setting is stored and try to enable it programmatically."""
import MetaTrader5 as mt5
import os

# Kill any running terminal first
import subprocess
subprocess.run(["taskkill", "/f", "/im", "terminal64.exe"], capture_output=True)

import time
time.sleep(3)

path = r"C:\Program Files\MetaTrader 5\terminal64.exe"
login = 1514130075
password = "...."
server = "FTMO-Demo"

# Initialize with timeout
if not mt5.initialize(path=path, login=login, password=password, server=server, timeout=30000):
    print(f"Init failed: {mt5.last_error()}")
    exit(1)

time.sleep(2)

term = mt5.terminal_info()
print(f"Connected: {term.connected}")
print(f"Trade allowed: {term.trade_allowed}")
print(f"Data path: {term.data_path}")

# Look for ini files that might store auto trading
data_path = term.data_path
for root, dirs, files in os.walk(data_path):
    for f in files:
        if f.endswith(".ini") or f.endswith(".dat"):
            full = os.path.join(root, f)
            size = os.path.getsize(full)
            if size > 0 and size < 100000:
                try:
                    with open(full, "rb") as fh:
                        content = fh.read().decode("utf-16-le", errors="ignore")
                        if "trade" in content.lower() or "auto" in content.lower() or "algo" in content.lower():
                            print(f"\nFound relevant file: {full} ({size} bytes)")
                            # Show relevant lines
                            for line in content.split("\n"):
                                if any(x in line.lower() for x in ["trade", "auto", "algo", "safe"]):
                                    print(f"  {line.strip()[:200]}")
                except:
                    pass

mt5.shutdown()
