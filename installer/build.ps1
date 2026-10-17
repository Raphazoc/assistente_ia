param([switch]$SomenteAplicativo)

$ErrorActionPreference = 'Stop'
$raizProjeto = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$pythonProjeto = Join-Path $raizProjeto '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonProjeto)) {
    throw 'Crie o ambiente .venv e instale requirements.txt antes de empacotar.'
}

Push-Location -LiteralPath $raizProjeto
try {
    & $pythonProjeto -m pip install -r requirements-build.txt
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar PyInstaller.' }
    & $pythonProjeto -m PyInstaller --noconfirm --clean AssistenteIA.spec
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao empacotar o aplicativo.' }
    $aplicativo = Join-Path $raizProjeto 'dist\AssistenteIA\AssistenteIA.exe'
    $verificacao = Start-Process -FilePath $aplicativo -ArgumentList '--smoke-test' -Wait -PassThru -WindowStyle Hidden
    if ($verificacao.ExitCode -ne 0) { throw 'O aplicativo empacotado não passou no teste de abertura.' }
    if ($SomenteAplicativo) { return }

    $candidatos = @(
        (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 7\ISCC.exe'),
        (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'),
        (Join-Path $env:ProgramFiles 'Inno Setup 6\ISCC.exe'),
        (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 7\ISCC.exe'),
        (Join-Path $env:ProgramFiles 'Inno Setup 7\ISCC.exe')
    )
    $compilador = $candidatos | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
    if (-not $compilador) {
        $comando = Get-Command ISCC.exe -ErrorAction SilentlyContinue
        if ($comando) { $compilador = $comando.Source }
    }
    if (-not $compilador) {
        throw 'Inno Setup não encontrado. Instale Inno Setup 6 ou 7 e execute este script novamente.'
    }
    & $compilador (Join-Path $raizProjeto 'installer\AssistenteIA.iss')
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao gerar o instalador.' }
    Write-Host (Join-Path $raizProjeto 'dist-installer\AssistenteIA-Setup.exe')
}
finally {
    Pop-Location
}
