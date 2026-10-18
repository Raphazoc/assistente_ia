# Assinatura do instalador Windows

Para publicar uma release, obtenha um certificado Authenticode de assinatura de
código emitido para o publicador do aplicativo. A assinatura não pode ser criada
de forma confiável apenas com o SHA-256 ou com um certificado autoassinado.

Configure estes secrets nas configurações do repositório GitHub:

| Secret | Conteúdo |
| --- | --- |
| `ASSISTENTE_PFX_BASE64` | Arquivo PFX convertido para Base64, sem quebras de linha. |
| `ASSISTENTE_PFX_PASSWORD` | Senha do PFX. |
| `ASSISTENTE_CERT_THUMBPRINT` | Thumbprint SHA-1 do certificado, sem espaços. |

O PFX nunca deve ser salvo no repositório, nos artefatos ou em logs. Para obter
o Base64 em PowerShell, use uma sessão privada e não salve o resultado em um
arquivo do projeto:

```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes('C:\caminho\certificado.pfx'))
```

O workflow de tag exige esses secrets, assina `AssistenteIA.exe` antes do Inno
Setup e assina `AssistenteIA-Setup.exe` depois. Ambos passam por verificação
Authenticode com carimbo de tempo; o instalador é validado novamente antes do
rascunho de release. O manifesto SHA-256 é calculado **após** a assinatura.
Sem certificado válido ou sem acesso ao serviço de timestamp, a release falha.

Após baixar um artefato, confirme localmente:

```powershell
Get-AuthenticodeSignature .\AssistenteIA-Setup.exe | Select-Object Status,SignerCertificate,TimeStamperCertificate
Get-FileHash .\AssistenteIA-Setup.exe -Algorithm SHA256
```
