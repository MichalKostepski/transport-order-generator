# Called by GitHub Actions after installing requirements and PyInstaller.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    $template = Join-Path $root "assets\template.pdf"
    if (-not (Test-Path $template)) { throw "Missing demonstration PDF template." }
    $buildArgs = @(
        "--noconfirm", "--clean", "--onedir", "--windowed",
        "--name", "TransportDeskDemo",
        "--paths", "$root",
        "--paths", (Join-Path $root "app"),
        "--add-data", "$template;assets",
        "demo/run_demo.py"
    )
    python -m PyInstaller @buildArgs
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed: $LASTEXITCODE" }
    $exe = Join-Path $root "dist\TransportDeskDemo\TransportDeskDemo.exe"
    if (-not (Test-Path $exe)) { throw "Expected executable missing: $exe" }
    Write-Host "Built: $exe"
}
finally {
    Pop-Location
}
