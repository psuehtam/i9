# Operação local v3

Atualizado em 23/09/2026. Este guia descreve a configuração local, não uma declaração de conclusão de todos os critérios do plano.

## Política atual de internet

As atualizações foram reativadas por solicitação do usuário em 23/09/2026. `.env`: `ALLOW_SOURCE_DOWNLOAD=true` e `I9_UPDATES_PAUSED=false`. As competências pendentes desde janeiro de 2026 podem ser retomadas; uma competência já concluída não deve ser baixada novamente.

O agendamento Windows cuida da saúde dos processos, dos backups e da descoberta de novas competências. A verificação periódica do supervisor é local; a descoberta remota é idempotente e downloads só são criados para competências ausentes ou revisões selecionadas. Reclassificar um mês já baixado usa o original preservado.

## Inicialização

- PostgreSQL portátil 17, dados em `data/runtime/postgres-data`, porta 55432, apenas loopback.
- `i9-Iniciar`: supervisor Python após login do usuário Windows.
- API e frontend compilado: `http://localhost:3000`.
- Trabalhador Python separado com fila PostgreSQL.
- `i9-Backup-Diario`: backup às 03h, executado quando possível se o computador estiver desligado no horário.
- Logs: `data/logs/api.log`, `worker.log`, `worker-console.log` e `data/runtime/postgres.log`.

O supervisor usa trava de arquivo para evitar duas instâncias, verifica a saúde e reinicia processos indisponíveis. O navegador não participa da execução. A primeira conta deve ser criada com `python -m scripts.setup_admin --username admin`, escolhendo uma senha de pelo menos 12 caracteres no terminal. Não existe senha padrão.

## Atualizações e falhas

A fila guarda jobs, tentativas e blocos. Reservas duram 120 segundos, com renovação a cada 30. Um token/época impede gravação de trabalhador com reserva vencida. Falhas transitórias aguardam 5, 30 e 120 minutos. Erros de formato exigem revisão.

Uma publicação em preparação não substitui a consulta pública. Revisões superadas e competências antigas não podem tomar o lugar de uma publicação operacional mais recente. Os IDs individuais independem da publicação.

O ZIP completo é preservado por hash. Linhas eletrificadas reconhecidas vão para o banco; nomes não classificados ficam em resumo por bloco. Nenhuma localização estatística é atribuída a um veículo pendente. Para ampliar a cobertura, registre evidência em Revisão de modelos e use Reaplicar classificação na execução concluída. A operação relê o original sem download.

## Backup

Execute `python -m scripts.operations backup`. O destino padrão é `data/backups`, substituível por `I9_BACKUP_DIR`. Cada pasta tem um dump PostgreSQL e manifesto. Os originais ficam em um diretório `originals` comum ao destino, identificados por hash, evitando sete cópias do mesmo arquivo dentro de cada backup diário.

Somente pastas de backup geradas pelo aplicativo, com manifesto e mais de 30 dias, são elegíveis à retenção. Os arquivos originais não são excluídos automaticamente. Monitore o espaço e configure um segundo equipamento/disco para proteção contra perda do computador.

Execute `python -m scripts.operations restore-test --path PASTA`. Isso cria outro banco, restaura o dump, verifica hashes, gira a época operacional e conta os registros. O relatório `restore-test.json` fica na pasta. O banco temporário de teste é removido; a base operacional não é substituída.

## Recuperação real

1. Pare supervisor, API e trabalhador; impeça também o ambiente anterior de voltar a escrever.
2. Preserve um backup do estado atual antes de qualquer reparo.
3. Restaure o dump em outro banco PostgreSQL, nunca sobre o banco atual com cadastros novos.
4. Disponibilize os originais referenciados no manifesto e confira seus hashes. Em outro computador, ajuste seus caminhos preservando o vínculo com cada artefato.
5. Aponte uma configuração isolada ao banco restaurado e execute `python -m src.worker --reset-epoch` com escritores ainda parados.
6. Confira IDs, vínculos, contagens, publicação selecionada e autorização; libere inicialmente só leitura.
7. Escolha um único ambiente escritor. Depois de novas escritas na v3, use reparo ou versão compatível; não restaure a base antiga sobre esses novos registros.

A instalação anterior e as cópias SQLite estão preservadas para comparação. Escritas v1/v2 foram desativadas. Não execute o importador legado `src.etl` sobre a configuração operacional v3.

## Limites de entrega

A cobertura da fonte não é universal. Modelos ambíguos, subclasses de eletrificação e categorias sem evidência dependem de revisão. A SENATRAN consultada fornece quantidades, não a relação de chassis e seriais individuais.

Os testes atuais cobrem geração, preservação de IDs, publicação, perdas de resposta, reservas expiradas, concorrência PostgreSQL, sessão, CSRF e passaporte. A certificação de todos os cenários extensivos do plano (incluindo fusões/divisões completas, evolução de significado dos campos e adaptação de todos os relatórios legados) ainda requer conclusão específica; não deve ser presumida a partir dos testes aprovados.
