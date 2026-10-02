# i9+ — Observatório da frota elétrica

Sistema em Python/FastAPI e painel em português para consultar frota BEV agregada, preservar referências mensais, associar baterias com rastreabilidade e comparar janelas de 8, 10 e 12 anos.

**Situação atual:** três camadas distintas. ABVE (~950 mil) é mercado acumulado. SENATRAN combustível (~888 mil em fev/2026) é a régua de cobertura. SENATRAN família (junho 205.816 e julho 222.373 no recorte publicado) é o mapa/bateria. Não some esses totais. O catálogo em `src/catalog.py` cobre BEV, PHEV e HEV com nome inequívoco; snapshots já publicados não ganham veículos novos. Agendador local às 02:00 de Brasília. Veja [docs/Evolucao_Battery_Intelligence.md](docs/Evolucao_Battery_Intelligence.md).

## Abrir o sistema

No PowerShell, na pasta deste projeto:

```powershell
pwsh -File scripts/start.ps1 -Install
```

Nas próximas vezes, omita `-Install`.

- Painel: <http://localhost:3000>
- API e documentação interativa: <http://127.0.0.1:8000/docs>
- Saúde da API: <http://127.0.0.1:8000/health>

Requisitos locais: Python 3.14 e Node.js 22.13 ou superior. As versões Python testadas estão em `requirements.lock.txt`; o frontend usa `dashboard/package-lock.json`. O comando de instalação requer internet.

Uma configuração `.env` local com chaves aleatórias foi criada durante o desenvolvimento, fora do controle de versão. A chave `ADMIN_API_KEY` dessa configuração permite usar **Atualizar base** e **Testar APIs** na aba **Fontes e qualidade**. Não compartilhe essa chave. As consultas de leitura são públicas no serviço local; produção requer rede privada ou autenticação no proxy.

## Dados reais e API da SENATRAN

O teste de 09/09/2026 encontrou 156 recursos no catálogo RENAVAM e nenhum com `datastore_active`. O `datastore_search` do recurso mais recente respondeu HTTP 400. Julho de 2026 é a referência mais recente encontrada, com ZIP de aproximadamente 136 MB.

Isso permite duas arquiteturas:

1. **Implementada:** o servidor descobre a referência pela API, baixa a fonte uma vez, trata os dados em blocos e entrega consultas pequenas pela API interna. O usuário não precisa abrir, enviar nem processar planilhas.
2. Uma API externa de registros realmente paginados, caso a i9+ disponha de fornecedor/credencial. Nenhum acesso desse tipo foi fornecido ou encontrado no catálogo público testado.

A opção autorizada já está habilitada no `.env` local. Em uma nova instalação, configure:

```dotenv
ALLOW_SOURCE_DOWNLOAD=true
```

Reinicie o servidor e use **Atualizar base**. A atualização busca a referência mais recente. Pela documentação interativa, também é possível enviar `{"reference":"2026-06"}` ao endpoint administrativo e importar o mês anterior.

Alternativa por linha de comando:

```powershell
$env:ALLOW_SOURCE_DOWNLOAD='true'
.venv/Scripts/python -m src.etl --reference 2026-07
```

**O parser foi validado com os arquivos reais de junho e julho de 2026.** Ausências de ano e localização são preservadas e indicadas no painel. A validação de quantidades não implica cobertura de todos os BEVs. A base ativa é `data/i9-validated-v2.db`, selecionada no `.env`; `data/i9.db` foi preservada para auditoria. Veja `docs/dataset-revision.json`.

## Ler o painel

O painel principal reúne **Visão geral**, **Veículos**, **Baterias**, **Análises**, **Fontes e atualização** e **Administração**. Em Veículos, alterne entre frota agregada e unidades individuais e filtre a categoria. Em Baterias, alterne entre unidades físicas e modelos técnicos. O acesso fica no botão Entrar do cabeçalho.

Para o cadastro guiado, entre como administrador e use **Cadastrar veículo e bateria** no Início ou **Cadastrar veículo** em Veículos. As etapas são veículo, escolha/criação da bateria e revisão do vínculo. A fonte autorizada é selecionada no primeiro passo. Se a bateria ou a data de instalação ainda não forem conhecidas, escolha **Vincular a bateria depois**. Somente a confirmação final salva os registros, em uma transação; conflitos cancelam toda a operação.

Usuários autorizados podem usar a busca conjunta de veículos e baterias no Início, em Veículos ou em Baterias, por placa, chassi, RENAVAM, marca/modelo, serial ou código. A busca mostra até 25 resultados e pede refinamento quando há mais; identificadores pesquisados não são gravados na auditoria. As pendências aparecem nas listas e nos detalhes. Administradores veem até seis cadastros com pendências entre os registros carregados na tela inicial.

Os detalhes individuais apresentam resumo, pendências e histórico visual de instalações/remoções; a bateria também mostra medições e eventos de uso. O passaporte fica em uma seção expansível, com progresso de preenchimento. Em Gerenciar bateria, administradores podem adicionar ou atualizar código, serial e identificador oficial com fonte autorizada.

Abra um veículo individual para criar uma bateria pendente, vincular uma bateria existente ou registrar uma remoção. Abra a bateria para consultar o passaporte e registrar medições. Essas operações exigem acesso administrativo e uma fonte restrita cadastrada. Criar um registro pendente não inventa serial e não comprova instalação. Os valores medidos de saúde e ciclos acompanham o histórico e não são alterados pelo formulário do passaporte.

Os relatórios mensais anteriores ficam em **Análises → Mapa, garantia e evolução**; atualização manual e testes de conexão ficam em **Fontes e atualização**, após entrar como administrador. A rota `/frota` continua disponível para compatibilidade.

- **Veículos no recorte:** soma das famílias classificadas. Compare com a régua SENATRAN por combustível (`official_ruler_pct`). Não é o acumulado ABVE.
- **Energia identificada:** quantidade × kWh ÷ 1.000, **separada por BEV/PHEV/HEV**. Pack híbrido é ~1 kWh; não misture com BEV.
- **Cobertura de bateria:** veículos com ficha aceita ÷ veículos do recorte.
- **Cobertura vs oficial:** famílias do recorte ÷ estoque SENATRAN por combustível (meta). Híbridos sem HEV no nome ficam de fora de propósito.
- **Janelas futuras:** ano de fabricação + 8/10/12. Não representa data certa de falha, descarte, perda de garantia ou capacidade residual.
- **Garantia:** ano de fabricação + prazo publicado. O início efetivo e a quilometragem não estão na base pública; o limite em km permanece explícito.
- **Evolução mensal:** compara o mês selecionado ao mês imediatamente anterior. Não substitui um mês ausente por outro mais antigo; variação líquida de estoque não equivale a novos emplacamentos.
- **Mapa:** malha generalizada oficial do IBGE. Clique em uma UF para filtrar. Cinza significa ausência de registros naquele recorte, não comprovação de frota zero.

Os filtros combinam referência, UF, município, marca, modelo, versão, ano, química, capacidade, ano de garantia, ano da janela, confiança e fonte. O ano da janela usa o cenário selecionado na aba de projeções. As exportações respeitam os filtros, exceto o catálogo técnico, que é independente do recorte.

## Cobertura inicial e limites

O catálogo de classificação está em `src/catalog.py` (`FAMILIES`): BEV, PHEV, HEV e HEV Flex com prefixos inequívocos. Nomes compartilhados com gasolina (`TOYOTA COROLLA`, `VOLVO XC40`, `PEUGEOT 208`) permanecem fora. Ampliar a lista só entra no **próximo** mês de ETL; junho e julho publicados são imutáveis em quantidade. Use `scripts/diagnose_unclassified.py` para priorizar a fila.

Fichas técnicas (`TECHNICAL_RULES`) colam por alias exato ou por família+ano quando existe **uma** regra. OpenEV continua candidato, sem auto-aprovação.

Não estão concluídos: 100% do baseline por combustível, VIN/telemetria, planilha de combustível mais nova que fev/2026, cubo interno do BI ABVE (só artigo revisado ou export licenciada como `registrations`), PostgreSQL/Airflow/Metabase neste computador e publicação em produção.

A ficha técnica efetivamente consultada do **BYD Dolphin GS**, revisada em 09/07/2026, informa 44,9 kWh, tecnologia Blade e garantia de 8 anos ou 200.000 km. A associação inicial está restrita ao ano 2026. Outros anos e versões ficam pendentes. A química não foi inferida apenas do nome comercial Blade e permanece ausente nessa regra.

A OpenEV global foi consultada pela API do GitHub e um candidato aplicável ao mercado BR foi salvo em `data/staging`. Ele traz uma regra global de garantia que não coincide com a ficha brasileira atual. Por isso, candidatos não são aprovados automaticamente. A atualização da base técnica precisa de revisão humana e uma nova versão da regra, sem sobrescrever a bateria de snapshots antigos.

## Testar

```powershell
.venv/Scripts/python -m pytest -q --junitxml=docs/test-results.xml
.venv/Scripts/python -m scripts.probe_apis
.venv/Scripts/python -m src.connectors.openev --make byd --model dolphin --year 2025
cd dashboard
npx tsc --noEmit
npm run build
```

Os testes de API/ETL usam banco isolado e dados sintéticos, nunca gravados na base do painel. Os probes externos usam requisições reais e salvam `docs/api-live-results.json`, além de aparecerem na aba de qualidade. Os testes unitários não exigem baixar o ZIP nacional. A validação adicional dos arquivos reais está em `docs/real-data-validation.json`; pode ser repetida, com a API e fontes locais disponíveis, por `.venv/Scripts/python -m scripts.validate_real`.

## PostgreSQL, Metabase e Airflow

Com Docker Desktop ativo e `.env` configurado:

```powershell
docker compose up -d --build postgres api
docker compose --profile bi up -d metabase
docker compose --profile scheduler up -d airflow
```

Pare a API Python local antes de iniciar a API Docker na porta 8000. Os bancos SQLite local e PostgreSQL são independentes; mudar a configuração não migra os dados existentes.

- PostgreSQL: porta local 5432, banco/usuário `i9`.
- Metabase: <http://localhost:3001>; aplicação usa PostgreSQL separado. No assistente inicial, cadastre a fonte com host `postgres`, porta 5432 e banco `i9`. Execute `docs/metabase.sql` para disponibilizar as visões de frota e cenários. Fixe uma versão validada da imagem Metabase antes de produção.
- Airflow: <http://localhost:8080>; modo standalone para homologação. Ative o DAG `i9_monthly_fleet`. Ele verifica diariamente às 05:00 UTC se há uma nova referência mensal e não recarrega snapshots existentes. O agendamento só existe quando o serviço está rodando e o DAG está ativo; nenhuma automação externa foi criada.

O Docker Compose foi validado sintaticamente. O daemon Docker estava indisponível no ambiente, portanto os contêineres não foram executados. Airflow standalone e o serviço único da API são adequados a esta homologação, não uma configuração de alta disponibilidade.

## Histórico, falhas e recuperação

- Brutos: `data/raw/AAAA-MM/senatran/<resource-id>.zip`, preservados com SHA-256.
- Download em blocos com arquivo temporário; somente arquivos completos recebem nome final.
- Tratamento em chunks de 100.000 linhas; retém o recorte de famílias eletrificadas, sem carregar a frota nacional inteira em memória.
- Duplicatas idênticas de origem são descartadas. Recortes distintos são agregados por município, nome e ano de fabricação.
- Uma transação publica snapshot e registros. Erro estrutural, município/UF inválido, ano impossível ou quantidade inválida impede publicação.
- `reference` é única: nenhuma recarga silenciosa. A correção de um snapshot já publicado exige procedimento de revisão versionada ainda a definir; a API não oferece exclusão.
- Correspondência exata/alias com ano aplicável pode vincular bateria. Similaridade textual produz apenas pendência.
- `POST /api/v1/admin/matches` registra aprovador e justificativa e acrescenta alias para cargas futuras; não reescreve históricos.
- Uma instância/worker da API deve executar o ETL. A trava de processo evita sobreposição nessa instância; a chave única no banco também bloqueia publicação duplicada. Não escale a execução para múltiplos workers sem trava distribuída/fila durável.
- Tarefas administrativas em background não são uma fila durável. Uma queda do processo pode deixar a execução com status `EXECUTANDO`; confira os logs e a existência do snapshot antes de reexecutar. Evoluir para worker dedicado é pendência de produção.

Backup PostgreSQL:

```powershell
pwsh -File scripts/backup.ps1
```

Preserve também `data/raw`, catálogo e código. Para restaurar, copie o dump para o contêiner e use `pg_restore` em **um banco novo de homologação**. Valide totais e referências antes de trocar a conexão. Não restaure por cima de produção sem um procedimento aprovado. A restauração não foi exercitada neste ambiente.

## Implantação

O painel foi construído com o starter Sites/Vinext e pode ser hospedado separadamente. A FastAPI, o PostgreSQL e o ETL exigem um servidor compatível com Python e armazenamento persistente. O runtime de hospedagem do frontend não substitui esses serviços. Não foi publicado um painel apontando para `localhost`, pois essa conexão não funcionaria para um serviço remoto.

Para produção, disponibilize a API em endereço HTTPS privado/autenticado e configure `I9_API_URL` no servidor do frontend. Defina acesso, backups, tratamento de filas, versão do Metabase e monitoração. Credenciais permanecem no ambiente do servidor.

## Fontes verificadas

- [SENATRAN — catálogo RENAVAM](https://dados.transportes.gov.br/api/3/action/package_show?id=registro-nacional-de-veiculos-automotores-renavam)
- [SENATRAN — frota 2026](https://www.gov.br/transportes/pt-br/assuntos/transito/conteudo-Senatran/frota-de-veiculos-2026)
- [IBGE — municípios](https://servicodados.ibge.gov.br/api/v1/localidades/municipios?view=nivelado)
- [IBGE — malha por UF](https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR?formato=application/vnd.geo%2Bjson&qualidade=minima&intrarregiao=UF)
- [INMETRO — PBE Veicular](https://www.gov.br/inmetro/pt-br/assuntos/regulamentacao/avaliacao-da-conformidade/programa-brasileiro-de-etiquetagem/tabelas-de-eficiencia-energetica/veiculos-automotivos-pbe-veicular)
- [BYD — Dolphin GS, revisão de julho/2026](https://www.byd.com/material/__CN/byd-site/br/fichas-tecnicas-2026/update-13-07-2026/07-13-2026---ficha-txiunica/BYD_DolphinGS_V2.pdf)
- [OpenEV — repositório oficial](https://github.com/open-ev-data/open-ev-data-dataset)
