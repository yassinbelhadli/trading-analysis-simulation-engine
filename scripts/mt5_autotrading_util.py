"""MT5 AutoTrading utility — enables trading via UI automation."""

import time
import sys
import os
import subprocess


def ensure_autotrading_enabled():
    """Ensure MT5 terminal has AutoTrading enabled.

    Returns True if trading is now available.
    Also returns on success/failure so caller can decide.
    """
    import MetaTrader5 as mt5

    path = r"C:\Program Files\MetaTrader 5\terminal64.exe"
    login = 1514130075
    password = "...."
    server = "FTMO-Demo"

    # ---- Step 1: kill any existing terminal ----
    subprocess.run(["taskkill", "/f", "/im", "terminal64.exe"],
                    capture_output=True)
    time.sleep(3)

    # ---- Step 2: start terminal via .exe with autoTrading flag ----
    # Use subprocess.Popen with DETACHED_PROCESS flag so we don't block
    CREATE_NO_WINDOW = 0x08000000
    proc = subprocess.Popen(
        [path,
         "/portable",
         f"/login:{login}",
         f"/password:{password}",
         f"/server:{server}",
         "/autoTrading"],
        close_fds=True,
        creationflags=subprocess.DETACHED_PROCESS | CREATE_NO_WINDOW,
    )
    print(f"Started MT5 (PID {proc.pid}) with /autoTrading")
    time.sleep(15)

    # ---- Step 3: connect via Python API ----
    if not mt5.initialize(path=path, timeout=30000):
        err = mt5.last_error()
        # If it fails because terminal is already connected, try login
        print(f"Init failed: {err}")
        if not mt5.initialize(path=path):
            print(f"Second init attempt failed: {mt5.last_error()}")
            return False
        else:
            # Already connected, try re-login
            if not mt5.login(login=login, password=password, server=server):
                print(f"Login failed: {mt5.last_error()}")
                # But might still be connected to correct account
                acc = mt5.account_info()
                if acc and acc.login == login:
                    print("Already logged in to correct account")

    term = mt5.terminal_info()
    print(f"trade_allowed={term.trade_allowed} connected={term.connected}")

    if term.trade_allowed:
        print("AutoTrading is ON")
        return True

    # ---- Step 4: try UI automation ----
    return _click_autotrading_button_via_uia(path)


def _click_autotrading_button_via_uia(path):
    """Use UIAutomation library to find and click AutoTrading button."""
    import MetaTrader5 as mt5

    try:
        import uiautomation as auto
    except ImportError:
        print("Installing uiautomation...")
        subprocess.run([sys.executable, "-m", "pip", "install", "uiautomation", "-q"],
                       capture_output=True)
        import uiautomation as auto

    # Find the MT5 window
    print("Searching for MT5 window via UIA...")
    mt5_window = auto.WindowControl(searchDepth=1, ClassName="MetaTrader5")
    if not mt5_window.Exists(3):
        print("MT5 window not found via UIA")
        return False

    mt5_window.SetFocus()
    print(f"Found MT5 window: '{mt5_window.Name}'")

    # Try to find the AutoTrading button
    # In MT5, the auto-trading button has a specific tooltip "Algo Trading"
    # It's usually a ToolBar control with specific buttons
    toolbars = mt5_window.ToolBarControl(searchDepth=5)
    print(f"Found {len(toolbars.GetChildren()) if hasattr(toolbars, 'GetChildren') else 0} toolbar children")

    # Try all buttons
    buttons = mt5_window.ButtonControl(searchDepth=5)
    all_buttons = buttons.GetChildren()
    print(f"Found {len(all_buttons)} buttons")

    for btn in all_buttons:
        name = btn.Name or ""
        help_text = ""
        try:
            help_text = btn.GetPropertyValue("HelpText") or ""
        except:
            pass
        leg_desc = ""
        try:
            leg_desc = btn.GetPropertyValue("LegacyHelpText") or ""
        except:
            pass

        combined = (name + " " + help_text + " " + leg_desc).lower()
        if any(kw in combined for kw in ["algo", "auto trade", "autotrade", "auto-trade"]):
            print(f"Clicking AutoTrading button: name='{name}'")
            btn.Click()
            time.sleep(3)
            break
    else:
        print("AutoTrading button not found by name. Listing all buttons:")
        for btn in all_buttons:
            try:
                print(f"  Button: name='{btn.Name}' rect={btn.BoundingRectangle}")
            except:
                pass

    # Check the result
    mt5.shutdown()
    if not mt5.initialize(path=path, timeout=30000):
        return False

    term = mt5.terminal_info()
    print(f"After click: trade_allowed={term.trade_allowed}")
    return term.trade_allowed


def try_via_powershell():
    """Try using PowerShell to enable AutoTrading via COM."""
    # This is a creative approach - use PowerShell to send keystrokes
    subprocess.run([
        "powershell", "-Command",
        """
        $wshell = New-Object -ComObject wscript.shell;
        $wshell.AppActivate('MetaTrader');
        Start-Sleep -Seconds 2;
        # Alt+T to open Tools menu, then A for Algo Trading
        $wshell.SendKeys('%t');
        Start-Sleep -Milliseconds 500;
        $wshell.SendKeys('a');
        """
    ], capture_output=True)
    time.sleep(3)


if __name__ == "__main__":
    result = ensure_autotrading_enabled()
    if result:
        print("SUCCESS: AutoTrading is enabled!")
    else:
        print("FAILED: Could not enable AutoTrading")
        sys.exit(1)
