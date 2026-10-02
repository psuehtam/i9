# Reconstrução v3 — registro de execução

Escopo da rodada: usar apenas julho de 2026, sem novo download, conforme solicitação de 18/09. Os demais meses e a descoberta automática estão pausados.

## Preservação

- SQLite operacional anterior preservado: `data/i9-validated-v2.db`.
- Outro SQLite anterior preservado: `data/i9.db`.
- Cópias iniciais: `data/backups/pre-reconstruction-20260916-144059`.
- Migração inicial para PostgreSQL: `data/migration/reconciliation.json`.
- 222.513 registros de veículo preservados. Destes, 222.373 estavam na publicação operacional antiga e 140 eram registros legados fora dessa publicação.
- Os 140 registros foram incorporados com origem de alocação separada; não consomem as sequências da SENATRAN nem entram automaticamente no total estatístico.
- Localização/ano que haviam sido copiados de agregados foram preservados como referência na auditoria e retirados da identidade individual pendente.
- Nenhuma bateria física existia na base migrada; nenhuma foi inventada.

## Alterações desta rodada

- PostgreSQL 17, migrações Alembic, API v3 e frontend na mesma origem.
- Navegação única: Veículos, Relatórios, Administração.
- URLs permanentes, IDs preservados, 50 fichas por página e competência presa na consulta paginada.
- Cadastro individual independente da competência ativa.
- Ficha preliminar virtual de 71 campos, revisão otimista e origem por valor.
- Baterias físicas separadas, vários packs, remoção com data desconhecida e medições tardias.
- Filtro antes da persistência: só observações reconhecidas como eletrificadas; os demais nomes permanecem resumidos para revisão.
- Leitura em blocos de 100 mil, memória limitada, checkpoint e gravação na mesma transação.
- Descarga HTTP por intervalos retomáveis, com versão/validador e checksum; não utilizada nesta rodada porque o arquivo de julho já estava completo.
- Fila persistida, tokens de reserva, retomada, bloqueios por modelo e publicação ordenada.
- Downloads desabilitados por configuração e sete jobs remotos pausados.
- Supervisor e backups agendados no Windows.

## Verificação

- O dump PostgreSQL de `postgres-20260917-094222` foi restaurado em banco isolado e conferido, antes desta carga: 222.513 veículos, 222.373 registros permanentes naquele momento e zero baterias físicas.
- Build TypeScript/Vite aprovado.
- Testes automatizados salvos em `data/migration/tests-v3-20260918.txt`.
- Navegador: lista de modelos, ID individual, ficha com 71 campos, expansão de campos, relatórios e filtro de estado conferidos. Cabeçalho mantido em todas essas páginas.
- Durante a leitura de 20 milhões de linhas, memória observada do trabalhador: cerca de 136 MB. Isso é uma amostra, não um teste de carga de todas as capacidades futuras.

## Pendências explícitas

Esta rodada não certifica a conclusão integral de todos os itens do plano original. Ainda exigem implementação/verificação específica: operações completas de fusão e divisão com desambiguação de aliases; migração de significado/tipos entre versões de esquema; adaptação atualizada de todos os relatórios v1/v2; bateria de testes extensivos de queda durante a troca real e recuperação após novas escritas; cobertura revisada de todos os modelos ambíguos.

A conta inicial precisa ser criada pelo usuário pelo procedimento local, escolhendo sua senha. A revisão automática bloqueou a tentativa de provisionar a credencial e alterar permissões de arquivos; não houve criação de senha padrão nem liberação da chave antiga.

O relatório de dados da carga local, ao concluir, fica em `data/migration/julho-2026-v3.json`. Não interpretar a estatística mensal como comprovação da identidade física dos veículos.


## Conferência em 23/09/2026

A carga local de julho terminou e está publicada: 22.690.877 linhas originais lidas, 58.421 observações eletrificadas detalhadas preservadas, 60 modelos e quantidade mensal de 469.873. Existem 470.013 cadastros permanentes visíveis, incluindo os 140 legados preservados separadamente. Há zero baterias físicas.

A cobertura continua parcial; 39.404 nomes não classificados estão resumidos para revisão. Isso não significa que todos esses nomes sejam elétricos: a origem inclui toda a frota e nomes ambíguos não são aceitos automaticamente.

Os testes finais dessa rodada registraram 122 aprovados, incluindo PostgreSQL real. Downloads permanecem desabilitados e as sete execuções remotas continuam pausadas. O supervisor está ativo. O relatório de contagens está em `data/migration/julho-2026-v3.json`.


Backup pós-carga validado em 23/09: `data/backups/postgres-20260923-094707`. Restauração isolada conferiu 470.013 veículos, 470.013 registros permanentes e zero baterias/vínculos físicos. Hashes dos originais e nova época operacional também verificados. O arquivo `restore-test.json` contém o resultado.

A listagem de modelos foi otimizada para agregar contadores uma vez por consulta, em lugar de varrer repetidamente os veículos de cada modelo. Medição local: aproximadamente 1,3 s após o ajuste (5,6 s observado antes, em condições de carga diferentes). Testes focados após o ajuste: 11 aprovados; os três testes PostgreSQL dessa invocação foram omitidos por falta da variável específica e já constam na execução completa anterior. A consulta nova também foi executada diretamente no PostgreSQL operacional e retornou os mesmos 60 modelos.
