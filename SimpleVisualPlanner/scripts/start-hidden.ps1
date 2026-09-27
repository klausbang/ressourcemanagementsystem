# Launches one hidden background process with its output redirected to files, and
# writes its PID to a file - the piece tunnel.bat can't do reliably in plain batch
# (starting a background process AND capturing its real PID at the same time).
# Called from tunnel.bat; not meant to be run by hand.
param(
    [Parameter(Mandatory = $true)][string]$FilePath,
    [Parameter(Mandatory = $true)][string]$ArgumentList,
    [Parameter(Mandatory = $true)][string]$WorkingDirectory,
    [Parameter(Mandatory = $true)][string]$StdOut,
    [Parameter(Mandatory = $true)][string]$StdErr,
    [Parameter(Mandatory = $true)][string]$PidFile
)

$proc = Start-Process `
    -FilePath $FilePath `
    -ArgumentList $ArgumentList `
    -WorkingDirectory $WorkingDirectory `
    -WindowStyle Hidden `
    -RedirectStandardOutput $StdOut `
    -RedirectStandardError $StdErr `
    -PassThru

Set-Content -Path $PidFile -Value $proc.Id -NoNewline
