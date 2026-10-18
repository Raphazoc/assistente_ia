param([Parameter(Mandatory=$true)][string]$Arquivo)

$ErrorActionPreference = 'Stop'
if (-not $env:ASSISTENTE_PFX_BASE64 -or -not $env:ASSISTENTE_PFX_PASSWORD -or -not $env:ASSISTENTE_CERT_THUMBPRINT) {
    throw 'Assinatura exige ASSISTENTE_PFX_BASE64, ASSISTENTE_PFX_PASSWORD e ASSISTENTE_CERT_THUMBPRINT.'
}
$destino = (Resolve-Path -LiteralPath $Arquivo).Path
$comando = Get-Command signtool.exe -ErrorAction SilentlyContinue
if ($comando) { $signtool = $comando.Source }
else {
    $sdk = Join-Path ${env:ProgramFiles(x86)} 'Windows Kits\10\bin'
    $signtool = Get-ChildItem -LiteralPath $sdk -Filter signtool.exe -Recurse -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -match '\\x64\\signtool\.exe$' } |
        Sort-Object FullName -Descending | Select-Object -First 1 -ExpandProperty FullName
}
if (-not $signtool) { throw 'signtool.exe do Windows SDK não encontrado.' }

$temporario = Join-Path ([IO.Path]::GetTempPath()) ([IO.Path]::GetRandomFileName() + '.pfx')
try {
    [IO.File]::WriteAllBytes($temporario, [Convert]::FromBase64String($env:ASSISTENTE_PFX_BASE64))
    & $signtool sign /f $temporario /p $env:ASSISTENTE_PFX_PASSWORD /fd SHA256 /tr https://timestamp.digicert.com /td SHA256 $destino
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao assinar o arquivo.' }
    & $signtool verify /pa /tw $destino
    if ($LASTEXITCODE -ne 0) { throw 'A validação Authenticode falhou.' }
    $assinatura = Get-AuthenticodeSignature -LiteralPath $destino
    if ($assinatura.Status -ne 'Valid' -or -not $assinatura.TimeStamperCertificate) {
        throw 'Assinatura ou carimbo de tempo inválido.'
    }
    $esperado = $env:ASSISTENTE_CERT_THUMBPRINT -replace '\s', ''
    if ($assinatura.SignerCertificate.Thumbprint -ine $esperado) {
        throw 'O certificado usado não corresponde ao thumbprint configurado.'
    }
    Write-Host "Assinatura validada: $($assinatura.SignerCertificate.Subject)"
}
finally {
    Remove-Item -LiteralPath $temporario -Force -ErrorAction SilentlyContinue
}
