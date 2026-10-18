# Segurança

Para relatar uma vulnerabilidade, prefira um [aviso de segurança privado do
GitHub](https://github.com/Raphazoc/assistente_ia/security/advisories/new),
se o recurso estiver disponível no repositório. Se não estiver, abra uma issue
com um resumo sem detalhes de exploração, dados pessoais ou chaves e peça um
canal privado para compartilhar os detalhes. Não publique credenciais,
conversas ou bancos de dados em issues.

O aplicativo é Beta. A pesquisa aplica autorização individual, filtro de
conteúdo adulto, limites de consulta e validação de URLs públicas. Páginas
externas são dados não confiáveis. Ações locais exigem confirmação antes de
serem executadas. Essas medidas reduzem riscos, mas não eliminam erros de
classificação ou de modelos generativos.

As chaves de API ficam no cofre do sistema. Builds locais podem continuar sem
assinatura. Uma release por tag agora exige certificado Authenticode, carimbo de
tempo e validação da assinatura no CI; sem certificado configurado, o pipeline
falha antes de criar o rascunho. Nenhum certificado foi fornecido ainda, portanto
o instalador gerado atualmente continua **sem assinatura** e não deve ser
apresentado como release assinada. O SHA-256 verifica apenas integridade em
relação ao manifesto, não autenticidade.

Na tela de atualização, a pessoa pode selecionar um instalador já baixado.
O aplicativo confere o digest SHA-256 informado pela API oficial da release,
valida a assinatura Authenticode no Windows e recusa versões iguais ou mais
antigas. A verificação não executa o instalador; builds locais sem assinatura
são recusadas por esse fluxo.
