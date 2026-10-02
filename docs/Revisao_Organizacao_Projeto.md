# Revisão da organização do projeto — 15/09/2026

Análise estática das páginas, APIs, modelos, processamento, inicialização, documentação e consulta de contagens no banco ativo. Não houve alteração dos fluxos nem dos dados. As sugestões abaixo são uma proposta de evolução, não funcionalidades já implementadas.

## Situação encontrada

O projeto evoluiu de um observatório de frota agregada para um sistema com veículos individuais, baterias físicas, instalações e passaportes. A interface ainda reproduz parte da organização inicial e expõe a estrutura das tabelas ao usuário.

O banco consultado contém 41.090 grupos de observações de veículos leves e 12 de ônibus; 90 veículos individuais com identidade `aggregate_derived`; nenhuma bateria física, instalação ou registro de passaporte salvo. Há suporte a caminhões no esquema, mas nenhuma observação atualmente classificada como `truck`. Acrescentar um modelo ao catálogo não cadastra automaticamente veículos físicos ou suas baterias.

## Ajustes prioritários

| Prioridade | Situação atual | Ajuste proposto | Evidência |
|---|---|---|---|
| Alta | `/frota` e `/inteligencia` oferecem navegações diferentes e funções sobrepostas. A página inicial reexporta a inteligência. | Uma navegação comum; preservar relatórios antigos dentro de Análises até migrar suas funções. | `dashboard/app/page.tsx`, `dashboard/app/frota/page.tsx`, `dashboard/app/inteligencia/page.tsx` |
| Alta | Ônibus têm aba própria com o mesmo fluxo de observações agregadas; falta filtro de categoria nessa interface. | Reunir categorias na consulta de frota com filtros de leves, caminhões, ônibus e motos, conservando fonte, período e medida. | Condicional `buses/observations` na página de inteligência; `Category` em `src/intelligence_models.py` |
| Alta | A aba Baterias lista modelos técnicos; baterias físicas estão no seletor de Ativos individuais. | Baterias com duas visões explícitas: unidades e modelos técnicos. Passaporte e histórico dentro de cada unidade. | Conteúdos `assets` e `batteries` na página de inteligência |
| Alta | Criar veículo, bateria e instalação exige trocar o tipo do formulário e transportar IDs. | Cadastro guiado de veículo com opção de vincular bateria existente ou criar registro pendente; selecionar registros por nome e código. Não presumir instalação comprovada nem inventar serial. | Formulário gerado a partir de `/contracts` e `create_entity` |
| Alta | Instalações, medições e remoção estão divididas entre um seletor de tabelas e Cadastros e importação. | Dentro do veículo: instalar/substituir bateria e consultar vínculos. Dentro da bateria: medições, eventos, segunda vida e histórico. | `assets`, `manage`, endpoints de instalações e ciclo de vida |
| Alta | Identificadores, estado de saúde e ciclos têm campos no cadastro físico e cópias editáveis no passaporte. O formulário envia todos os valores; as cópias salvas prevalecem sobre dados atuais. | Definir a origem de cada campo; dados dinâmicos seguem medições com data e fonte. Editar apenas campos próprios do passaporte e evitar congelar valores herdados. | `passport_data`, `save_passport` e componente `Passport` |
| Média | Fontes e qualidade aparecem nos dois painéis; baixar, atualizar e sincronizar são operações espalhadas. | Uma área Fontes e atualização com execuções, falhas de sincronização, revisão técnica e importação por arquivo. | `quality` no painel antigo; `sources/manage` no novo; `src/etl.py` registra `intelligence_sync_error` |
| Média | Janelas futuras e Oportunidades tratam planejamento com apresentações e premissas diferentes. | Uma área Análises com cenários, mapa, garantia e evolução mensal; mostrar premissas por relatório. | `forecast/monthly` no painel antigo e `opportunities` no novo |
| Média | Revisar compatibilidade exige digitar ID da evidência em uma área genérica. | Fila de revisão no catálogo técnico, com origem, versão/ano, aprovação e publicação acessíveis a partir do registro. | Conteúdo `manage` e endpoints `/evidence/{key}/review` e `/publish` |
| Média | Login está dentro de Cadastros e importação; identificação e auditoria aparecem como operações de cadastro. | Acesso global na navegação, Administração para permissões/auditoria e identificação dentro do veículo. | `unlock`, `manage`, `/vehicles/{key}/identify`, `/audit` |

## Ajustes de dados e manutenção

- A migração do legado atribui `vehicle_category='light'` a observações e especificações. Ampliar o catálogo para veículos pesados requer propagar a categoria real e revisar a classificação em versões futuras; trocar abas não resolve esse dado. Evidência: `src/intelligence.py:migrate`.
- A migração das baterias do legado atribui fonte BYD de forma fixa. Se esse catálogo receber fichas de outros fabricantes, a origem precisa ser escolhida pela evidência de cada ficha. Não reatribuir históricos sem revisão. Evidência: `src/intelligence.py:migrate`.
- Os 71 campos são textos livres. Capacidade, tensão, porcentagens e datas precisam de unidades e validação; documentos precisam de referências; temperatura e carga históricas precisam de observações datadas. O último valor não substitui o histórico descrito nos campos 70 e 71. Evidência: `PassportUpdate`, catálogo `src/battery_passport.py` e `passport_data`.
- Completude é calculada com a mesma média para registros de naturezas diferentes, incluindo identidade individual no catálogo técnico. Separar completude técnica, identificação do veículo e completude do passaporte. Evidência: `src/intelligence.py:quality`.
- O painel antigo ainda depende da API v1 e das tabelas legadas; a v2 espelha parte desses dados e registra novos cadastros próprios. Planejar uma fonte principal para consultas e manter os dados antigos como histórico, sem remover a v1 antes de migrar os relatórios necessários.
- Textos de operação ainda citam BEV, regras antigas, arquivos de código e nomes internos. Atualizar README, metadados e mensagens para o escopo atual e levar detalhes de implementação à documentação administrativa.
- Agendador local e Airflow são alternativas de execução. A administração deve indicar qual está ativo; não ativar ambos inadvertidamente. Não é necessário unificar esses mecanismos no código para reunir seu acompanhamento na interface.

## Separações que devem continuar

Reunir a navegação não significa somar estoque SENATRAN com emplacamentos ABVE, nem misturar períodos ou coberturas. Modelos técnicos e baterias físicas continuam entidades distintas. Registros derivados de agregados continuam diferentes de veículos identificados. Um veículo pode ter múltiplos packs e várias instalações ao longo do tempo; a interface deve admitir isso. Identificadores e telemetria continuam sujeitos às permissões existentes.

## Organização proposta

1. Visão geral: indicadores e pendências, com fontes e períodos explícitos.
2. Veículos: todas as categorias; visões de frota agregada e unidades individuais. Unidade → baterias atuais/anteriormente instaladas.
3. Baterias: unidades físicas e catálogo técnico. Unidade → passaporte, saúde, medições, eventos e histórico de veículos.
4. Análises: mapa, cenários, garantia e evolução mensal.
5. Fontes e atualização: fontes, importações, execução, qualidade e revisão de evidências.
6. Administração: acesso, permissões e auditoria.

Começar pela navegação e nomenclatura, depois pelo cadastro e pelas operações dentro dos registros. Corrigir a origem e atualização dos campos do passaporte antes de depender dele como registro operacional. Migrar consultas legadas por último, com comparação de totais e preservação de snapshots.
