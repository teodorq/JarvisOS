Option Explicit

Dim shell, files, root, pythonw, main, command
Set shell = CreateObject("WScript.Shell")
Set files = CreateObject("Scripting.FileSystemObject")

root = files.GetParentFolderName(WScript.ScriptFullName)
pythonw = files.BuildPath(root, ".venv\Scripts\pythonw.exe")
main = files.BuildPath(root, "main.py")

If Not files.FileExists(pythonw) Then
    pythonw = "pythonw.exe"
End If

command = Chr(34) & pythonw & Chr(34) & " " & Chr(34) & main & Chr(34)
shell.CurrentDirectory = root
shell.Run command, 0, False
