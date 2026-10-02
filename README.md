# i9+ — Veículos e baterias

O i9 organiza os dados mensais da SENATRAN no fluxo **Veículos → modelo → cadastro individual → ficha da bateria**. Relatórios e Administração usam a mesma estrutura visual.

## Instalação recomendada

Para uma instalação nova, use Docker Desktop. Ele inicia PostgreSQL 17, aplica as migrações, compila o frontend e mantém a API e o trabalhador em processos separados.

Requisitos:

- Git;
- Docker Desktop com Docker Compose;
- pelo menos 15 GB livres para baixar e processar uma competência mensal com margem;
- conexão estável durante o download inicial.

No PowerShell:

```powershell
git clone URL_DO_REPOSITORIO
cd i9
Copy-Item .env.example .env
```

Abra o `.env` e troque `POSTGRES_PASSWORD` e `ADMIN_API_KEY` por valores longos e diferentes. Use letras e números na senha do PostgreSQL. Para permitir o download manual, configure:

```dotenv
ALLOW_SOURCE_DOWNLOAD=true
I9_UPDATES_PAUSED=true
```

`I9_UPDATES_PAUSED=true` impede verificações automáticas; o comando manual abaixo continua funcionando e baixa somente o mês pedido.

Inicie o sistema e crie a primeira conta administrativa:

```powershell
docker compose up --build -d
docker compose exec api python -m scripts.setup_admin --username admin
```

A aplicação estará em http://localhost:8000/veiculos e a documentação da API em http://localhost:8000/docs.

### Baixar somente um mês

Use uma competência encerrada no formato `AAAA-MM`:

```powershell
docker compose exec worker python -m scripts.download_month --reference 2026-08
```

O comando consulta o catálogo oficial, baixa somente os conjuntos encontrados para essa competência, mostra o progresso e processa o conteúdo. O arquivo principal de marca/modelo costuma ter centenas de megabytes compactado e dezenas de milhões de linhas; o processamento usa disco adicional temporariamente. Uma interrupção pode ser retomada sem duplicar os blocos confirmados.

Se a competência ainda não foi publicada, o comando termina informando a ausência. Se ela já estiver concluída, não baixa o arquivo novamente. Para verificar uma revisão posterior do mesmo mês, acrescente `--refresh`.

O clone do GitHub não contém dados da frota. ZIPs originais, banco, arquivos temporários e credenciais são criados localmente e estão excluídos pelo `.gitignore`.

## Instalação local no Windows

Para desenvolvimento, com Python 3.14 e Node.js 22 instalados:

```powershell
Copy-Item .env.example .env
pwsh -File scripts/start.ps1 -Install
```

Acesse http://localhost:3000/veiculos. Sem `DATABASE_URL`, essa forma usa SQLite e serve apenas para desenvolvimento e prévia. Para importações mensais reais, prefira PostgreSQL pelo Docker.

Depois da instalação inicial, inicie com:

```powershell
pwsh -File scripts/start.ps1
```

Para baixar uma competência nessa instalação, habilite `ALLOW_SOURCE_DOWNLOAD=true` no `.env` e execute:

```powershell
.venv/Scripts/python.exe -m scripts.download_month --reference 2026-08
```

## Administrador

Leituras são públicas. Alterações exigem sessão administrativa e proteção CSRF. Não existe senha padrão.

Para criar a conta em uma instalação local e escolher a senha quando solicitado:

```powershell
.venv/Scripts/python.exe -m scripts.setup_admin --username admin
```

Para recuperar a conta, use o mesmo comando com `--reset`. A troca invalida as sessões existentes. Depois entre em `/admin`.

## Como interpretar os registros

- **Publicados no mês:** estatística de uma única competência da SENATRAN.
- **Cadastros existentes:** fichas permanentes com ID interno. A quantidade pode superar a estatística de um mês posterior.
- **Veículos identificados:** fichas que receberam identificação individual informada ou verificada.
- **Com bateria vinculada:** veículos com registro de pack físico.

Os meses não são somados. A sequência 90 → 95 → 85 → 92 mantém 95 fichas, sem alegar quais carros saíram ou voltaram. Cada ficha abre por URL própria e mantém seu ID.

Uma ficha estatística não prova a identidade de um carro. Placa, chassi, RENAVAM, localização individual e serial permanecem vazios enquanto desconhecidos. Os filtros de estado e município dos relatórios representam a estatística, não a localização dos cadastros pendentes.

A ficha preliminar contém os 71 campos do cliente, com estados pendente, rascunho, confirmado e não aplicável. Ela não cria uma bateria física. Packs são registrados quando existe evidência individual, com vínculos e eventos separados.

## Importação SENATRAN

O importador lê o original em blocos de até 100 mil linhas, filtra as famílias eletrificadas reconhecidas e guarda somente essas observações detalhadas no PostgreSQL. Nomes não reconhecidos são resumidos para revisão. O original compactado é preservado com hash; aprovar uma nova classificação permite reler o arquivo local.

A cobertura é parcial e explícita: nomes que não permitem distinguir combustão de híbrido não são classificados por suposição. Categoria desconhecida não vira automaticamente automóvel.

O trabalhador é separado da API. Fila, tentativas, checkpoints e reservas ficam no PostgreSQL. A nova publicação só entra no ar depois de terminar a preparação e validar as contagens. Downloads remotos habilitados usam trechos verificáveis e retomáveis.

Para processar um arquivo já disponível, sem internet:

```powershell
.venv/Scripts/python.exe -m src.worker --once --no-schedule --import-file CAMINHO_DO_ZIP --reference 2026-07
```

A retomada preserva os blocos confirmados. Administração mostra execução, erro e progresso. A reclassificação administrativa usa os arquivos originais preservados.

## Atualização automática e backups

Para ativar a consulta diária das competências fechadas, configure `I9_UPDATES_PAUSED=false`. O sistema consulta a fonte oficial, mas não baixa novamente uma competência concluída. No Windows, `scripts/install-tasks.ps1` configura início após login e backup diário às 03h. Fechar o navegador não interrompe o trabalhador; desligar o computador adia o processamento.

```powershell
.venv/Scripts/python.exe -m scripts.operations backup
.venv/Scripts/python.exe -m scripts.operations restore-test --path CAMINHO_DO_BACKUP
```

O backup contém o dump PostgreSQL e o manifesto dos originais. Configure `I9_BACKUP_DIR` para outro disco ou destino adequado. Cópias somente neste computador não protegem contra perda do equipamento. Consulte `docs/Operacao-v3.md`.

## Desenvolvimento e validação

O backend usa Python, FastAPI, SQLAlchemy, Alembic e PostgreSQL 17. O frontend usa React, React Router e Vite e é servido pela própria API após o build.

```powershell
.venv/Scripts/python.exe -m pytest -q
Set-Location dashboard
npm.cmd run build
```

Testes de concorrência exigem `I9_TEST_DATABASE_URL` e usam esquemas descartáveis isolados. Não execute ferramentas que apaguem a base operacional. A documentação histórica anterior está em `docs/README-anterior-v3.md`.
