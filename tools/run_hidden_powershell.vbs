Option Explicit

Dim shell, files, powershellPath, scriptPath, command, index, exitCode

If WScript.Arguments.Count < 1 Then
    WScript.Quit 2
End If

Set shell = CreateObject("WScript.Shell")
Set files = CreateObject("Scripting.FileSystemObject")

scriptPath = files.GetAbsolutePathName(WScript.Arguments(0))
If Not files.FileExists(scriptPath) Then
    WScript.Quit 3
End If
If LCase(files.GetExtensionName(scriptPath)) <> "ps1" Then
    WScript.Quit 4
End If

powershellPath = shell.ExpandEnvironmentStrings( _
    "%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" _
)
command = QuoteArgument(powershellPath) & _
    " -NoProfile -NonInteractive -ExecutionPolicy Bypass" & _
    " -WindowStyle Hidden -File " & QuoteArgument(scriptPath)

For index = 1 To WScript.Arguments.Count - 1
    command = command & " " & QuoteArgument(WScript.Arguments(index))
Next

shell.CurrentDirectory = files.GetParentFolderName(scriptPath)
exitCode = shell.Run(command, 0, True)
WScript.Quit exitCode

Function QuoteArgument(value)
    QuoteArgument = Chr(34) & _
        Replace(CStr(value), Chr(34), Chr(34) & Chr(34)) & _
        Chr(34)
End Function
