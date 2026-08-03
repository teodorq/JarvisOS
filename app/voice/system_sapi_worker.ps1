param()

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Speech

$Synthesizer = [System.Speech.Synthesis.SpeechSynthesizer]::new()
[Console]::Out.WriteLine("READY")
[Console]::Out.Flush()

try {
    while (($Line = [Console]::In.ReadLine()) -ne $null) {
        if ($Line -eq "__CLOSE__") {
            break
        }

        $Parts = $Line.Split("`t", 4)
        if ($Parts.Count -ne 4) {
            [Console]::Out.WriteLine("ERROR`tunknown`tNieprawidlowe dane")
            [Console]::Out.Flush()
            continue
        }

        $RequestId = $Parts[0]
        try {
            $WordsPerMinute = [int]$Parts[1]
            $Volume = [double]::Parse(
                $Parts[2],
                [System.Globalization.CultureInfo]::InvariantCulture
            )
            $Text = [System.Text.Encoding]::UTF8.GetString(
                [Convert]::FromBase64String($Parts[3])
            )

            $SapiRate = [Math]::Round(($WordsPerMinute - 170) / 18.0)
            $Synthesizer.Rate = [Math]::Max(-10, [Math]::Min(10, $SapiRate))
            $Synthesizer.Volume = [Math]::Max(
                0,
                [Math]::Min(100, [Math]::Round($Volume * 100))
            )
            $Synthesizer.Speak($Text)
            [Console]::Out.WriteLine("OK`t$RequestId")
        }
        catch {
            $Message = ($_.Exception.Message -replace "[\r\n\t]+", " ").Trim()
            [Console]::Out.WriteLine("ERROR`t$RequestId`t$Message")
        }
        [Console]::Out.Flush()
    }
}
finally {
    $Synthesizer.Dispose()
}
