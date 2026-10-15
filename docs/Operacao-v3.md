# Operação local

A instalação atual usa os scripts `instalar.bat` e `iniciar.bat`. A Administração mostra o progresso da importação da SENATRAN e permite escolher o modo real ou fictício do dashboard Oportunidades.

## Importação mensal

A SENATRAN fornece arquivos agregados por mês. O NEXUS importa apenas modelos classificados como elétricos ou híbridos com evidência; nomes ambíguos ficam para revisão. Os arquivos completos são temporários. Após a publicação validada, a reclassificação exige novo download e comparação do hash da fonte.

Relatórios complementares sem combustível não permitem isolar os eletrificados. Deles permanece somente a referência de publicação. A lista de modelos e quantidades vem do arquivo de marca/modelo.

## Oportunidades

O modo real mostra baterias individualmente vinculadas e medidas. A visão regional usa apenas quantidades agregadas e idade dos veículos, sem identificar um carro. O modo fictício gera perfis de demonstração em leitura para os veículos cadastrados e mostra os 71 campos por bateria fictícia, sem gravá-los no cadastro real.

O limite inicial de saúde é 80% e pode ser alterado em Administração. Para integrar medições reais, siga [Integração de baterias](Integracao_Baterias.md).

## Atualização de instalações existentes

Com a API e o trabalhador parados, execute `python -m scripts.migrate_electrified_retention` para conferir o volume legado e depois `python -m scripts.migrate_electrified_retention --apply` para remover resumos e arquivos completos antigos. Reimporte cada competência instalada pelo painel ou com `python -m scripts.download_month --reference AAAA-MM --refresh`. A publicação antiga continua ativa até a nova passar pela conferência de totais. O reprocessamento requer novo download oficial.
