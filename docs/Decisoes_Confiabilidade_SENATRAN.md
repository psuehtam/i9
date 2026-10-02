# Revisão de confiabilidade do plano SENATRAN

Data: 16/09/2026.

Status: decisões de arquitetura para a reconstrução; **não são garantias já implementadas no sistema atual**. Este adendo complementa o plano apresentado na conversa e substitui suas regras nos pontos abaixo. Não foi encontrado um `PLAN.md` no projeto durante esta revisão. O documento enviado em Downloads foi tratado como material de análise, sem executar suas sugestões automaticamente.

## Evidências no código atual

- `src/fleet_publication.py`: usa transações por lote e IDs determinísticos, mas faz consulta seguida de inserção sem reserva explícita por modelo. Colisões podem causar falhas; isso não significa que toda corrida necessariamente crie duplicatas, pois já existem chaves únicas. A conclusão de uma publicação pode trocar a ativa sem comparar sua competência com a atual.
- `src/intelligence_schema.py`: já há unicidade para VIN, RENAVAM, placa e algumas associações. Faltam as estruturas novas de execução, tentativas, blocos, aliases e versões de fichas. A ficha atual armazena JSON sem versão própria do esquema.
- `src/transform/ingest.py`: já lê CSV com `chunksize=100000`. Entretanto, `seen`, `aggregated`, `identities` e `skipped` crescem durante o arquivo; portanto, leitura em blocos não garante memória limitada no processamento completo.
- `src/api/fleet.py`: a consulta de veículo exige associação com a publicação ativa; um cadastro preservado no banco pode ficar inacessível após uma queda estatística.
- `tests/test_fleet_publication.py`: cobre exemplos sequenciais e publicação parcial. O teste de falha altera o estado manualmente; não provoca queda real entre gravações nem disputa entre processos.

## Decisões para os 15 pontos da revisão

### 1. Não haverá reativação estatística de veículos físicos

A unidade permanente e a quantidade mensal são entidades diferentes. Não será selecionado um conjunto de IDs para afirmar quais carros compõem cada mês.

Para o mesmo modelo canônico, a capacidade de fichas derivadas da fonte cresce até a maior quantidade nacional necessária nas publicações aceitas e nunca diminui automaticamente. A consulta usa `sequence ASC, id ASC`, mas a ordem é apenas de navegação.

Exemplo obrigatório: 90 → 95 → 85 → 92 resulta em 95 fichas preservadas e quantidades mensais independentes. Na última consulta, a interface mostra “92 publicados no mês / 95 cadastros existentes”. Não marca dez veículos específicos como baixados em abril nem sete como reativados em maio.

Contadores distinguem fichas derivadas de estatística e cadastros reais recebidos de outras fontes. Uma identificação confirmada pode promover uma ficha existente; entradas sem correspondência segura não consomem fichas arbitrariamente nem são somadas à estatística oficial. Eventual conciliação exige evidência e auditoria.

### 2. Concorrência protegida no banco

Cada modelo canônico terá uma linha permanente e um contador de sequências. A criação de fichas obtém `SELECT ... FOR UPDATE` nessa linha, recalcula a necessidade, insere até 1.000 fichas e atualiza o contador na mesma transação.

Usar `READ COMMITTED` com bloqueios explícitos e restrições, não exigir `SERIALIZABLE` em todas as operações. Inserir a linha do modelo com chave única antes de bloqueá-la; uma consulta que não encontra linha não reserva um modelo inexistente. Todos os escritores de fichas derivadas usam o mesmo serviço. Em operações com vários modelos, bloquear por ID crescente.

Garantias adicionais: `UNIQUE(model_id, sequence)` e `UNIQUE(public_code)`. O código público será persistido, não recalculado a partir de nomes ou hashes curtos mutáveis. Deadlocks e falhas transitórias reiniciam a transação inteira, com tentativas limitadas. Não ignorar qualquer conflito indiscriminadamente: verificar se corresponde ao mesmo resultado esperado.

### 3. Lote, resultado e progresso são atômicos

Adicionar blocos com `UNIQUE(job_id, stage, block_index)`. O plano de blocos e seu tamanho ficam congelados ao iniciar a execução. Cada bloco registra intervalo/chave de entrada e resumo do resultado.

Gravações de domínio, estado concluído do bloco e checkpoint são confirmados na mesma transação. Se houver falha antes do commit, tudo é desfeito; depois do commit, a retomada identifica o bloco concluído. A chave do bloco complementa, mas não substitui, as chaves únicas dos veículos e observações.

Testar explicitamente commit confirmado pelo banco com perda da resposta ao trabalhador. Progresso exibido deve ser derivado dos blocos confirmados, não de incrementos externos sujeitos a repetição.

### 4. Separar hash físico e equivalência dos dados

Preservar `raw_sha256` dos bytes recebidos como prova do arquivo. Adicionar `semantic_sha256`, calculado sobre registros normalizados antes da classificação.

A normalização terá versão, tipos explícitos, distinção entre nulo/zero/vazio e serialização canônica. Não remover dimensão ou texto semanticamente relevante. Ordenar as linhas canônicas no banco, com ordenação determinística, e alimentar o hash por cursor; nunca ordenar todo o arquivo em RAM. Preservar multiplicidade das linhas: duplicatas só podem ser eliminadas por regra documentada daquele dataset, não por igualdade presumida.

Mudança só de compressão, timestamp do ZIP ou ordem não gera revisão pública dos dados. O novo download permanece rastreável. Mudança de quantidade, dimensão ou multiplicidade gera conteúdo diferente. Hash igual em competências distintas não elimina uma competência.

### 5. Streaming em toda a cadeia

Manter leitura pandas em blocos de até 100.000 linhas, com gravação intermediária em lotes menores e limites de tamanho já validados. Transferir agregação, ordenação e deduplicação para tabelas/indexações do PostgreSQL. Retirar coleções Python que crescem com o arquivo inteiro.

Registrar tamanho comprimido, descomprimido, linhas, duração e pico de memória. Teste de memória deve incluir dados majoritariamente únicos; arquivo de linhas repetidas não evidencia crescimento de `set` ou dicionário. Faltar espaço em disco bloqueia a preparação e mantém a publicação anterior.

### 6. Unicidade de identificadores com escopo e histórico

Manter validação de formato na aplicação e unicidade no banco sobre identificadores normalizados. Campos sem identificação ficam nulos, nunca vazios ou preenchidos com “pendente”.

No registro de identificadores, usar escopo explícito `(tipo, emissor, valor_normalizado)` e unicidade para atribuições vigentes. VIN/RENAVAM confirmados não podem identificar dois veículos; mudança de proprietário do identificador exige correção auditada. Placas têm histórico e não serão tratadas isoladamente como prova suficiente de identidade física. Serial de bateria precisa do escopo do fabricante/emissor; sem esse contexto, permanece uma alegação pendente.

Conflitos retornam 409 com informação apropriada ao usuário autenticado. Não juntar cadastros automaticamente. Restrições de vínculo atual de baterias também residem no banco, com transação para encerrar/abrir vínculos e validação do histórico temporal.

### 7. IDs antigos resolvidos desde a primeira migração

Adicionar `entity_alias(entity_type, namespace, old_id, canonical_id)` com unicidade dos três primeiros campos. Preservar o UUID original sempre que possível; aliases são necessários quando identidade ou rota muda.

Cada alias aponta diretamente para um destino canônico, sem cadeias ou ciclos. A migração valida existência do destino e colisões. Links antigos de modelos por publicação preservam a referência histórica na navegação, sem afirmar que o grupo antigo é o mês atual. Não escolher um destino por similaridade de texto.

Uma fusão com destino único pode redirecionar. Uma divisão em vários modelos mostra opções/desambiguação, sem encaminhar arbitrariamente. Consultar aliases antes de devolver 404.

### 8. Resultado do parse persistido e reutilizável

Guardar observações normalizadas de todas as linhas do dataset selecionado, inclusive as ainda não classificadas, com origem, competência, membro do arquivo, posição e versão do parser. As dimensões originais relevantes e a quantidade permanecem disponíveis.

Classificação é uma etapa separada e versionada. Mudança de catálogo reclassifica essa base, sem novo download ou parse. Mudança do próprio parser ou da normalização exige reconstrução a partir do original. Não chamar o original de mera prova: ele também permite recuperação e correção do parser.

Interromper o parse pode exigir reler um membro comprimido até o checkpoint; nesse caso, as linhas já confirmadas são reconhecidas por posição e não reinseridas. Não prometer acesso aleatório eficiente em ZIP.

### 9. Reservas recuperadas e trabalhadores antigos invalidados

Persistir proprietário, vencimento, token de geração da reserva e época operacional. O trabalhador renova a reserva a cada 30 segundos; validade inicial de 120 segundos. As gravações de cada bloco verificam e bloqueiam a reserva na mesma transação, rejeitando token antigo.

Recuperar tarefas expiradas no início do trabalhador e periodicamente, não somente no boot do computador. Um trabalhador que perdeu a reserva não pode confirmar dados ao voltar.

Após restore: parar todos os escritores, entrar em manutenção, criar nova época operacional, invalidar reservas antigas, verificar arquivos referenciados pelo backup e só então liberar a fila. O procedimento precisa isolar o ambiente restaurado do antigo; token no banco não impede um processo de continuar escrevendo em outro banco ainda ativo.

### 10. Alertas reproduzíveis

Configurações de thresholds são versões imutáveis com autor, data, motivo e valores. Alteração cria nova versão e auditoria na mesma transação.

Cada avaliação armazena versão da política, publicações comparadas, métricas e resultado. Mudança da configuração não reescreve alertas históricos; reavaliar cria um novo resultado. A regra escolhida pelo usuário continua: anomalia estatística válida publica com alerta; falha estrutural bloqueia.

### 11. Compatibilidade por contrato, não por fotografia congelada

Implementar adaptador de leitura v1/v2 sobre o novo domínio. Congelar o contrato JSON, filtros, paginação e semântica documentada, não os dados exibidos. Uma view pode ajudar internamente, mas não protege sozinha serialização, autenticação ou rotas.

Criar testes específicos dos contratos legados e testes próprios da v3; eles não são necessariamente iguais. Comparar totais somente quando competência, cobertura e filtros forem equivalentes. Escritas legadas ficam bloqueadas após o corte. Não devolver sucesso vazio para esconder incompatibilidade.

### 12. Concorrência testada separadamente da carga

Usar PostgreSQL real e conexões/processos independentes. Sincronizar testes por barreiras/eventos e pontos de falha; `sleep` arbitrário não será a garantia de que a corrida aconteceu.

Cenários: dois trabalhadores para o mesmo modelo; reserva vencida retomada por outro; trabalhador antigo tentando confirmar; queda antes/depois do commit; queda na troca da publicação; escrita administrativa durante migração; duas identificações simultâneas iguais.

Carga mede latência, memória, disco e tempo total. Concorrência verifica invariantes e resultados sob interleavings forçados. Cada espera tem timeout para evitar suíte travada.

### 13. Evolução das fichas sem perder valores

Ficha e revisão armazenam `schema_version`. Campos têm IDs semânticos estáveis, tipo, unidade e regras. Renomear um rótulo mantém a identidade; mudar o significado cria outro campo. Campo descontinuado permanece legível no histórico.

Migrações possuem chave única `(record_id, from_version, to_version, migration_version)`, preservam a revisão original e criam nova revisão. Conversão comprovadamente sem perda pode ser automática; valor incompatível fica pendente de revisão, sem truncamento, descarte ou confirmação artificial. Guardar origem e transformação.

A API informa versão da ficha e aceita controle otimista de revisão. Edição contra revisão antiga retorna 409. A primeira definição mantém os 71 campos do cliente; futuras definições exibem seu próprio total, sem fingir que versões diferentes são idênticas.

### 14. Rollback com limite explícito

Não reativar automaticamente escritas antigas depois de novos dados entrarem no sistema reconstruído.

Procedimento do corte:

1. Ensaiar migração em cópia e registrar contagens, IDs e verificações de integridade.
2. Bloquear escritas antigas, parar importadores, aguardar transações e fazer backup final consistente de banco/arquivos.
3. Migrar; abrir aplicação nova em leitura e validar rotas, contratos, contagens e autenticação sem aceitar escritas de negócio.
4. Se falhar antes da liberação de escritores, voltar ao banco/aplicação preservados; registrar a tentativa e sua reversão.
5. Registrar checkpoint do corte e liberar os escritores novos.

O marco conservador é a liberação dos escritores novos. Depois dele, preservar o novo banco e usar correção progressiva, manutenção ou uma versão anterior comprovadamente compatível com esse esquema. Não restaurar snapshot antigo sobre dados novos. Voltar ao modelo antigo após esse marco exige procedimento separado de migração reversa/reconciliação com todas as escritas, não um botão de rollback.

Manter somente um ambiente autorizado a escrever. Restrições/esquemas antigos não serão removidos na mesma entrega que faz o corte.

### 15. Deduplicação por estágio, com contexto da fonte

Todas as colunas destas chaves são `NOT NULL`; ausências legítimas são modeladas fora delas. Não depender de `UNIQUE` com valores nulos para garantir exclusão.

| Entidade | Chave única de negócio |
| --- | --- |
| Parse | fonte + dataset + competência + raw_sha256 + versão_parser + versão_normalização |
| Conteúdo semântico | fonte + dataset + competência + versão_normalização + semantic_sha256 |
| Classificação/publicação preparada | conteúdo_semântico_id + versão_regras + versão_transformação |
| Bloco | job_id + etapa + índice_bloco |
| Ficha derivada | modelo_canônico_id + sequência |
| Código público | código persistido |
| Alias | tipo_entidade + namespace + identificador_antigo |

Execução lógica e tentativas ficam separadas: retomar falha cria tentativa, não outro trabalho lógico. Arquivos diferentes semanticamente equivalentes podem ter parses diferentes e convergir para o mesmo conteúdo. Não usar hash sem fonte/dataset/competência: isso poderia eliminar legitimamente dois meses iguais. Não incluir thresholds na chave de importação; avaliações de alertas têm suas próprias versões.

## Dois controles adicionais necessários

### Publicação fora de ordem

Bloquear a linha da publicação ativa durante a troca. Competência inferior nunca substitui a mais recente. Para revisões do mesmo mês, uma geração monotônica aprovada identifica a revisão desejada; resultado atrasado de geração superada pode ficar no histórico, mas não virar ativo. Conclusão exige igualdade das contagens planejadas e verificadas, não apenas `>=`.

### Compatibilidade com dados existentes

Antes de adicionar constraints, diagnosticar duplicatas, códigos antigos ambíguos e valores incompatíveis. Separar casos para revisão sem descartar silenciosamente linhas. A migração deve falhar de forma recuperável quando não consegue provar uma associação. Novas versões não transformam especificação genérica herdada em medição individual confirmada.

## Ordem e aceite da implementação

1. Definir tabelas, chaves, aliases, contratos de ficha e migrações antes de gerar novos cadastros.
2. Implementar parse persistido, hashes, classificação e execução por blocos.
3. Implementar reservas, tokens, publicação ordenada e auditoria de configuração.
4. Integrar API/interface e contratos legados.
5. Ensaiar restore, corte e rollback antes da atualização real.

Além dos testes do plano original, exigir: sequência 90/95/85/92; equivalência de arquivos com ordem/ZIP diferentes; distinção de competências com conteúdo igual; multiplicidade preservada; correção de parser; ID antigo após fusão/divisão; migração incompatível dos campos; revisão mensal concluindo fora de ordem; restauração durante execução; falhas antes/depois do marco de corte.

Esta revisão foi estática. Nenhuma migração, publicação, importação ou alteração do código de execução foi realizada. As garantias só poderão ser declaradas implementadas após os testes acima.

## Referências técnicas

As escolhas de bloqueios e restrições seguem os mecanismos documentados do PostgreSQL; os detalhes de domínio e o procedimento de corte são decisões deste projeto.

- [Bloqueios explícitos](https://www.postgresql.org/docs/current/explicit-locking.html)
- [Restrições e unicidade](https://www.postgresql.org/docs/current/ddl-constraints.html)
- [Isolamento de transações](https://www.postgresql.org/docs/current/transaction-iso.html)
