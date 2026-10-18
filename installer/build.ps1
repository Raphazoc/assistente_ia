param([switch]$SomenteAplicativo)

$ErrorActionPreference = 'Stop'
$raizProjeto = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$pythonProjeto = Join-Path $raizProjeto '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonProjeto)) {
    throw 'Crie o ambiente .venv e instale requirements.txt antes de empacotar.'
}
$scriptInstalador = Join-Path $raizProjeto 'installer\AssistenteIA.iss'

Push-Location -LiteralPath $raizProjeto
try {
    $versaoCodigo = (& $pythonProjeto -c 'from app.versao import VERSAO; print(VERSAO)').Trim()
    if ($LASTEXITCODE -ne 0) { throw 'Não foi possível ler a versão do aplicativo.' }
    $versaoInstalador = [regex]::Match(
        [IO.File]::ReadAllText($scriptInstalador), '(?m)^AppVersion=([^\r\n]+)'
    ).Groups[1].Value.Trim()
    if ($versaoCodigo -ne $versaoInstalador) {
        throw "Versões diferentes: aplicativo $versaoCodigo e instalador $versaoInstalador."
    }
    & $pythonProjeto -m pip install -r requirements-build.txt
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar PyInstaller.' }
    & $pythonProjeto -m PyInstaller --noconfirm --clean AssistenteIA.spec
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao empacotar o aplicativo.' }
    $aplicativo = Join-Path $raizProjeto 'dist\AssistenteIA\AssistenteIA.exe'
    $verificacao = Start-Process -FilePath $aplicativo -ArgumentList '--smoke-test' -Wait -PassThru -WindowStyle Hidden
    if ($verificacao.ExitCode -ne 0) { throw 'O aplicativo empacotado não passou no teste de abertura.' }
    if ($env:ASSISTENTE_SIGNING_REQUIRED -eq '1') {
        & (Join-Path $PSScriptRoot 'sign.ps1') -Arquivo $aplicativo
        if ($LASTEXITCODE -ne 0) { throw 'Falha na assinatura do aplicativo.' }
    }
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
    & $compilador $scriptInstalador
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao gerar o instalador.' }
    $instalador = Join-Path $raizProjeto 'dist-installer\AssistenteIA-Setup.exe'
    if (-not (Test-Path -LiteralPath $instalador)) { throw 'Instalador não encontrado após a compilação.' }
    if ($env:ASSISTENTE_SIGNING_REQUIRED -eq '1') {
        & (Join-Path $PSScriptRoot 'sign.ps1') -Arquivo $instalador
        if ($LASTEXITCODE -ne 0) { throw 'Falha na assinatura do instalador.' }
    }
    $sha256 = (Get-FileHash -LiteralPath $instalador -Algorithm SHA256).Hash.ToLowerInvariant()
    $manifesto = "$instalador.sha256"
    Set-Content -LiteralPath $manifesto -Value "$sha256  AssistenteIA-Setup.exe" -Encoding ascii
    Write-Host $instalador
    Write-Host "SHA-256: $sha256"
}
finally {
    Pop-Location
}
