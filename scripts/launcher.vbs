Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\Users\AGA GAMING\Desktop\test saas"
WshShell.Run "cmd.exe /c set PYTHONPATH=C:\Users\AGA GAMING\Desktop\test saas && ""C:\Users\AGA GAMING\Desktop\test saas\.venv\Scripts\python.exe"" -m scripts.background_runner", 0, False
