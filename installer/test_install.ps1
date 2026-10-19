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
    if ($env:ASSISTENTE_SIGNING_REQUIRED -eq '1') {
        $esperado = $env:ASSISTENTE_CERT_THUMBPRINT -replace '\s', ''
        if (-not $esperado) { throw 'Thumbprint obrigatório para validar o aplicativo instalado.' }
        foreach ($alvo in @($arquivo, $executavel)) {
            $assinatura = Get-AuthenticodeSignature -LiteralPath $alvo
            if ($assinatura.Status -ne 'Valid' -or -not $assinatura.TimeStamperCertificate -or
                $assinatura.SignerCertificate.Thumbprint -ine $esperado) {
                throw "Assinatura Authenticode inválida ou certificado inesperado: $alvo"
            }
        }
    }
    $recursos = Join-Path $destino '_internal\resources'
    foreach ($necessario in @(
        $executavel,
        (Join-Path $recursos 'vozes\pt_BR-faber-medium.onnx'),
        (Join-Path $recursos 'config_geral.json'),
        (Join-Path $recursos 'config_servicos.json'),
        (Join-Path $recursos 'assistente_ia.ico'),
        (Join-Path $recursos 'assistente_ia.png')
    )) {
        if (-not (Test-Path -LiteralPath $necessario -PathType Leaf)) {
            throw "Recurso ausente após instalar: $(Split-Path -Leaf $necessario)."
        }
    }
    $abertura = Start-Process -FilePath $executavel -ArgumentList '--smoke-test' -Wait -PassThru -WindowStyle Hidden
    if ($abertura.ExitCode -ne 0) { throw 'O aplicativo instalado não passou no teste de abertura.' }

    New-Item -ItemType Directory -Path $dadosUsuario -Force | Out-Null
    $bancoTeste = Join-Path $dadosUsuario 'memoria.db'
    $diarioTeste = Join-Path $dadosUsuario 'memoria.db-wal'
    $backupsTeste = Join-Path $dadosUsuario 'backups'
    $configuracaoTeste = Join-Path $dadosUsuario 'config_geral.json'
    $perfilTeste = Join-Path $dadosUsuario 'perfil_voz.json'
    Set-Content -LiteralPath $bancoTeste -Value 'memoria anterior' -Encoding utf8
    Set-Content -LiteralPath $diarioTeste -Value 'diario anterior' -Encoding utf8
    New-Item -ItemType Directory -Path $backupsTeste -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $backupsTeste 'copia.db') -Value 'backup anterior' -Encoding utf8
    Set-Content -LiteralPath $configuracaoTeste -Value 'configuracao preservada' -Encoding utf8
    Set-Content -LiteralPath $perfilTeste -Value 'perfil anterior' -Encoding utf8
    $atualizacao = Start-Process -FilePath $arquivo -ArgumentList @(
        '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/NOICONS', "/DIR=`"$destino`""
    ) -Wait -PassThru -WindowStyle Hidden
    if ($atualizacao.ExitCode -ne 0) { throw "Reinstalação falhou (código $($atualizacao.ExitCode))." }
    foreach ($antigo in @($bancoTeste, $diarioTeste, $backupsTeste, $perfilTeste)) {
        if (Test-Path -LiteralPath $antigo) { throw "Memória antiga permaneceu após reinstalar: $antigo" }
    }
    if ((Get-Content -LiteralPath $configuracaoTeste -Raw).Trim() -ne 'configuracao preservada') {
        throw 'A reinstalação alterou a configuração do usuário.'
    }
    if (-not (Test-Path -LiteralPath (Join-Path $dadosUsuario 'reiniciar_memoria.flag'))) {
        throw 'O instalador não marcou a primeira abertura para confirmação da limpeza.'
    }
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
Remove-Item -LiteralPath $configuracaoTeste
if (@(Get-ChildItem -LiteralPath $dadosUsuario -Force).Count -eq 0) {
    Remove-Item -LiteralPath $dadosUsuario
}
