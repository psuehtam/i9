# Interface operacional do NEXUS

Aplicação React + Vite + React Router. O código ativo fica em `src/`. O frontend antigo em Next.js foi retirado; versões anteriores podem ser consultadas no histórico do Git. Backups locais não acompanham o repositório.

## Desenvolvimento

Com Node.js 22.13 ou superior, execute `npm ci` e `npm run dev`. A interface atende em `http://127.0.0.1:3000`; `/api` é encaminhado à API em `http://127.0.0.1:8000`. A variável `I9_API_URL` pode substituir o destino no ambiente de desenvolvimento. Para o uso comum no Windows, siga os atalhos descritos no [README principal](../README.md).

Execute `npm run lint` e `npm run build` para validar. O build inclui a verificação de tipos; `npm run typecheck` permite executá-la separadamente. O resultado está em `dist/`. Em produção, a API serve esse diretório e o fallback de rotas; `vite preview` serve apenas para inspeção local do build. Não versione `node_modules` nem `dist`; versione `package-lock.json` junto com alterações nas dependências.

## Rotas

- `/` redireciona para `/veiculos`.
- `/veiculos` lista modelos e mantém filtros e publicação na URL.
- `/veiculos/modelos/:id` lista fichas permanentes paginadas.
- `/veiculos/unidades/:id` mostra identificação, ficha e baterias físicas.
- `/veiculos/unidades/:id/ficha-bateria` mostra os 71 campos preliminares.
- `/baterias/:id` mostra o pack, instalações, eventos e passaporte.
- `/relatorios` mostra estatísticas de uma competência e filtros geográficos.
- `/admin` fornece acesso autenticado, execução de atualizações e revisão.

Compatibilidade: `/inteligencia` leva a `/veiculos`; suas áreas `dados`, `importar`, `admin` e `acesso` levam a `/admin`; `relatorios` leva a `/relatorios`. `/frota` leva a `/relatorios`. Os IDs antigos de entidades são resolvidos pela API, sem correspondência aproximada no navegador.

## Sessão e edição

A sessão utiliza cookie da mesma origem e token CSRF em memória. Não há chave administrativa nem senha em localStorage/sessionStorage. Cada ficha é salva com revisão esperada; conflitos preservam o rascunho na tela. Dados preliminares não criam ativos físicos.

## Contratos

Os tipos operacionais ficam em `src/api.ts`. Todas as consultas utilizam `/api/v3`. Em Veículos, a referência padrão é a publicação mais recente; escolher outro mês grava `publication_id` na URL. Os relatórios mantêm uma competência por consulta. Valores ausentes são exibidos como pendentes, sem estimativa ou dados demonstrativos.

Administração consulta as fontes oficiais e permite importar um mês por solicitação. O processamento continua no servidor quando a aba é fechada, desde que os serviços estejam ligados. A lista diferencia a importação de marca/modelo dos arquivos complementares. Os relatórios mostram dados agregados dos modelos reconhecidos; a antiga tabela de planilhas brutas não faz parte da interface.
