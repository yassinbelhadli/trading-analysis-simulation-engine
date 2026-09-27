"""Enable AutoTrading in MT5 terminal by simulating button click."""

import time
import MetaTrader5 as mt5


def find_mt5_window():
    """Find the main MT5 terminal window using win32gui."""
    import win32gui
    import win32con

    class WindowFinder:
        def __init__(self):
            self.target = None

        def callback(self, hwnd, _):
            title = win32gui.GetWindowText(hwnd)
            cls = win32gui.GetClassName(hwnd)
            # MT5 main window class is usually "MetaTrader5" or similar
            if "MetaTrader" in cls and win32gui.IsWindowVisible(hwnd):
                self.target = hwnd
                return False
            # Also try by title
            if "MetaTrader 5" in title and "FTMO" in title:
                self.target = hwnd
                return False
            return True

        def find(self):
            win32gui.EnumWindows(self.callback, None)
            return self.target

    finder = WindowFinder()
    hwnd = finder.find()

    if hwnd:
        # Get window title
        title = win32gui.GetWindowText(hwnd)
        cls = win32gui.GetClassName(hwnd)
        print(f"Found MT5 window: hwnd={hwnd} title='{title}' class='{cls}'")
        return hwnd
    return None


def click_autotrading_button_via_python():
    """Use the MT5 Python API's terminal info to check and the MT5 API to toggle.

    There's actually a way to set this: restart the terminal with specific flags.
    """
    import subprocess
    import os

    # Kill all existing MT5 terminals
    subprocess.run(["taskkill", "/f", "/im", "terminal64.exe"],
                    capture_output=True)
    time.sleep(2)

    path = r"C:\Program Files\MetaTrader 5\terminal64.exe"
    login = 1514130075
    password = "....."
    server = "FTMO-Demo"

    # Start MT5 via win32api with autoTrading flag
    import win32api
    import win32con

    # Start with autoTrading flag
    try:
        proc = win32api.ShellExecute(
            0, "open", path,
            f"/portable /login:{login} /password:{password} /server:{server} /autoTrading",
            None, win32con.SW_SHOWNORMAL,
        )
        print(f"ShellExecute returned: {proc}")
    except Exception as e:
        print(f"ShellExecute failed: {e}")
        return False

    time.sleep(15)

    # Now connect via MT5 API
    if not mt5.initialize(path=path, timeout=30000):
        print(f"MT5 init failed: {mt5.last_error()}")
        return False

    term = mt5.terminal_info()
    print(f"Terminal: trade_allowed={term.trade_allowed} connected={term.connected}")

    if not term.trade_allowed:
        print("AutoTrading still OFF after restart")
        return False

    return True


def click_autotrading_with_uia():
    """Use UIAutomation to find and click AutoTrading button."""
    try:
        import uiautomation as auto
    except ImportError:
        print("uiautomation not available, installing...")
        import subprocess
        subprocess.run([
            "pip", "install", "uiautomation"
        ], capture_output=True)
        import uiautomation as auto

    # Find the MT5 window
    mt5_window = auto.WindowControl(searchDepth=1, ClassName="MetaTrader5")
    if not mt5_window.Exists(3):
        print("MT5 window not found via UIA")
        return False

    mt5_window.SetFocus()
    print(f"Found MT5 window: {mt5_window.Name}")

    # The AutoTrading button is a toolbar button. Search for it.
    # In MT5, it's usually a button in the toolbar with tooltip "Algo Trading"
    btn = mt5_window.ButtonControl(searchDepth=5)
    found_buttons = []
    for b in btn.GetChildren():
        name = b.Name or ""
        if "algo" in name.lower() or "auto" in name.lower() or "trade" in name.lower():
            found_buttons.append(b)

    if found_buttons:
        print(f"Found AutoTrading button: {found_buttons[0].Name}")
        found_buttons[0].Click()
        time.sleep(2)
        return True

    # Try finding by AutomationId or by tooltip
    try:
        control = mt5_window.ControlControl(
            searchDepth=5, AutomationId="4098"
        )
        if control.Exists(1):
            control.Click()
            print("Clicked AutoTrading button by AutomationId")
            time.sleep(2)
            return True
    except:
        pass

    print("Could not find AutoTrading button via UIA")
    return False


if __name__ == "__main__":
    import sys
    method = sys.argv[1] if len(sys.argv) > 1 else "restart"

    if method == "restart":
        result = click_autotrading_button_via_python()
    elif method == "uia":
        result = click_autotrading_with_uia()
    else:
        print("Usage: enable_mt5_autotrading.py [restart|uia]")
        sys.exit(1)

    if result:
        print("AutoTrading enabled!")
    else:
        print("Failed to enable AutoTrading")
        sys.exit(1)
