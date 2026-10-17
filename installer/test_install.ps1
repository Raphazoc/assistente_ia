param([Parameter(Mandatory = $true)][string]$Instalador)

$ErrorActionPreference = 'Stop'
$arquivo = (Resolve-Path -LiteralPath $Instalador).Path
if ((Split-Path -Leaf $arquivo) -ne 'AssistenteIA-Setup.exe') {
    throw 'Informe o instalador AssistenteIA-Setup.exe gerado pelo projeto.'
}
$manifesto = "$arquivo.sha256"
if (-not (Test-Path -LiteralPath $manifesto)) { throw 'Arquivo SHA-256 não encontrado.' }
$linha = (Get-Content -LiteralPath $manifesto -Raw).Trim()
if ($linha -notmatch '^([0-9a-fA-F]{64})  AssistenteIA-Setup\.exe$') {
    throw 'Formato do arquivo SHA-256 inválido.'
}
$sha256 = (Get-FileHash -LiteralPath $arquivo -Algorithm SHA256).Hash
if ($sha256 -ine $Matches[1]) { throw 'O SHA-256 do instalador não corresponde ao manifesto.' }

if (-not $env:RUNNER_TEMP -or -not $env:LOCALAPPDATA) {
    throw 'Execute este teste em um runner Windows descartável.'
}
$raizTemporaria = [IO.Path]::GetFullPath($env:RUNNER_TEMP).TrimEnd('\')
$destino = [IO.Path]::GetFullPath((Join-Path $raizTemporaria 'AssistenteIA-Instalacao-Teste'))
if (-not $destino.StartsWith($raizTemporaria + '\', [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Destino da instalação fora da pasta temporária do runner.'
}
$dadosUsuario = Join-Path $env:LOCALAPPDATA 'AssistenteIA'
$instalacaoExistente = Join-Path $env:LOCALAPPDATA 'Programs\AssistenteIA'
$registroExistente = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\{6C479E2C-7C41-48B9-84B3-F26814F15727}_is1'
if ((Test-Path -LiteralPath $destino) -or (Test-Path -LiteralPath $dadosUsuario) -or
    (Test-Path -LiteralPath $instalacaoExistente) -or (Test-Path -LiteralPath $registroExistente)) {
    throw 'Este teste exige uma conta Windows sem instalação ou dados anteriores da assistente.'
}

$instalado = $false
$desinstalado = $false
try {
    $processo = Start-Process -FilePath $arquivo -ArgumentList @(
        '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/NOICONS', "/DIR=`"$destino`""
    ) -Wait -PassThru -WindowStyle Hidden
    if ($processo.ExitCode -ne 0) { throw "Instalação falhou (código $($processo.ExitCode))." }
    $instalado = $true
    $executavel = Join-Path $destino 'AssistenteIA.exe'
    $recursos = Join-Path $destino '_internal\resources'
    foreach ($necessario in @(
        $executavel,
        (Join-Path $recursos 'vozes\pt_BR-faber-medium.onnx'),
        (Join-Path $recursos 'config_geral.json'),
        (Join-Path $recursos 'config_servicos.json')
    )) {
        if (-not (Test-Path -LiteralPath $necessario -PathType Leaf)) {
            throw "Recurso ausente após instalar: $(Split-Path -Leaf $necessario)."
        }
    }
    $abertura = Start-Process -FilePath $executavel -ArgumentList '--smoke-test' -Wait -PassThru -WindowStyle Hidden
    if ($abertura.ExitCode -ne 0) { throw 'O aplicativo instalado não passou no teste de abertura.' }

    New-Item -ItemType Directory -Path $dadosUsuario -Force | Out-Null
    $sentinela = Join-Path $dadosUsuario 'dados-do-usuario-teste.txt'
    Set-Content -LiteralPath $sentinela -Value 'preservar após desinstalar' -Encoding utf8
    Write-Host 'Instalação e abertura do executável: OK.'
}
finally {
    if ($instalado) {
        $desinstaladores = @(Get-ChildItem -LiteralPath $destino -Filter 'unins*.exe' -File)
        if ($desinstaladores.Count -ne 1) { throw 'Desinstalador não encontrado ou ambíguo.' }
        $processo = Start-Process -FilePath $desinstaladores[0].FullName -ArgumentList @(
            '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART'
        ) -Wait -PassThru -WindowStyle Hidden
        if ($processo.ExitCode -ne 0) { throw "Desinstalação falhou (código $($processo.ExitCode))." }
        $desinstalado = $true
    }
}
if (-not $desinstalado) { throw 'A instalação não pôde ser verificada.' }
for ($tentativa = 0; $tentativa -lt 20 -and (Test-Path -LiteralPath $destino); $tentativa++) {
    Start-Sleep -Milliseconds 500
}
if (Test-Path -LiteralPath (Join-Path $destino 'AssistenteIA.exe')) {
    throw 'O executável permaneceu após a desinstalação.'
}
if (-not (Test-Path -LiteralPath $sentinela -PathType Leaf)) {
    throw 'A desinstalação removeu dados pessoais fora da pasta do programa.'
}
$sobras = @(Get-ChildItem -LiteralPath $destino -Recurse -File -ErrorAction SilentlyContinue)
if ($sobras.Count -gt 0) { throw 'Arquivos do programa permaneceram após a desinstalação.' }
Write-Host 'Desinstalação removeu o programa e preservou os dados do usuário: OK.'
Write-Host "Assinatura digital: $((Get-AuthenticodeSignature -FilePath $arquivo).Status)"
Remove-Item -LiteralPath $sentinela
if (@(Get-ChildItem -LiteralPath $dadosUsuario -Force).Count -eq 0) {
    Remove-Item -LiteralPath $dadosUsuario
}
