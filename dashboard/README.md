# Interface operacional do i9

Aplicação React + Vite + React Router. As páginas de `app/` foram preservadas como referência legada e não participam do build.

## Desenvolvimento

Execute `npm ci`, `npm run dev`. A interface atende em `http://127.0.0.1:3000`; `/api` é encaminhado à API em `http://127.0.0.1:8000`. A variável `I9_API_URL` pode substituir o destino no ambiente de desenvolvimento.

Execute `npm run build` e `npm run typecheck` para validar. O resultado está em `dist/`. Em produção, a API serve esse diretório e o fallback de rotas; `vite preview` serve apenas para inspeção local do build.

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

Os tipos operacionais ficam em `src/api.ts`. Todas as consultas utilizam `/api/v3`; páginas estatísticas fixam `publication_id` na URL após a primeira resposta. Valores ausentes são exibidos como pendentes, sem estimativa ou dados demonstrativos.
