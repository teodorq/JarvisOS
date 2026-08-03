param(
    [Parameter(Mandatory = $true)][string]$TextBase64,
    [string]$VoiceId = "",
    [int]$Rate = 158,
    [double]$Volume = 0.92,
    [double]$Pitch = 0.88,
    [string]$OutputPath = ""
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Runtime.WindowsRuntime

function Wait-WinRt($Operation, [Type]$ResultType) {
    $Method = [System.WindowsRuntimeSystemExtensions].GetMethods() |
        Where-Object {
            $_.Name -eq "AsTask" -and $_.IsGenericMethod -and
            $_.GetParameters().Count -eq 1
        } | Select-Object -First 1
    $Task = $Method.MakeGenericMethod($ResultType).Invoke($null, @($Operation))
    $Task.Wait()
    return $Task.Result
}

$SynthType = [Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media.SpeechSynthesis, ContentType=WindowsRuntime]
$StreamType = [Windows.Media.SpeechSynthesis.SpeechSynthesisStream, Windows.Media.SpeechSynthesis, ContentType=WindowsRuntime]
$Text = [System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($TextBase64))
$Synth = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::new()
$Voice = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices |
    Where-Object { $_.Id -eq $VoiceId } | Select-Object -First 1
if ($null -eq $Voice) {
    $Voice = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices |
        Where-Object { $_.Language -eq "pl-PL" } | Select-Object -First 1
}
if ($null -ne $Voice) { $Synth.Voice = $Voice }
$Synth.Options.SpeakingRate = [Math]::Max(0.5, [Math]::Min(2.0, $Rate / 200.0))
$Synth.Options.AudioVolume = [Math]::Max(0.25, [Math]::Min(1.0, $Volume))
try {
    $Synth.Options.AudioPitch = [Math]::Max(0.7, [Math]::Min(1.2, $Pitch))
} catch {}
$Speech = Wait-WinRt ($Synth.SynthesizeTextToStreamAsync($Text)) $StreamType
$NetStream = [System.IO.WindowsRuntimeStreamExtensions]::AsStreamForRead($Speech)
try {
    if ($OutputPath) {
        $Output = [System.IO.File]::Create($OutputPath)
        try { $NetStream.CopyTo($Output) } finally { $Output.Dispose() }
    } else {
        $Player = [System.Media.SoundPlayer]::new($NetStream)
        $Player.PlaySync()
    }
} finally {
    $NetStream.Dispose()
    $Speech.Dispose()
    $Synth.Dispose()
}
