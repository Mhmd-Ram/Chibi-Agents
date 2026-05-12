' Launch the chibi daemon with no visible console.
' Double-click to run, or call from a startup shortcut.
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = scriptDir
' pythonw is the no-console Python interpreter on Windows.
sh.Run "pythonw -m daemon", 0, False
