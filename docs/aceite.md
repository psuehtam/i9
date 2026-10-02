# Validação do plano técnico

| Requisito | Situação verificável |
|---|---|
| API Python com endpoints previstos | Implementada; testes HTTP locais e automatizados |
| Filtros de município, ano, marca/modelo e bateria | Implementados na API e no painel |
| Fontes externas por API | Catálogo SENATRAN, IBGE e GitHub acessíveis; API de registros SENATRAN indisponível no recurso consultado |
| Processar um mês real | Junho e julho de 2026 processados: 205.816 e 222.373 veículos no recorte |
| Preservar histórico mensal | Dois meses reais preservados; repetição retorna SEM_NOVIDADE |
| Base completa de BEVs | Parcial: 12 famílias revisadas; painel explicita o recorte |
| Conjunto representativo de baterias | Parcial: associação validada cobre 18.397 veículos de julho (8,3%); candidatos OpenEV em staging |
| Fonte por campo técnico | Implementada em provenance; nunca inferir dados ausentes |
| Matching e revisão | Exato/alias aplicável por ano; fuzzy não vincula; API administrativa de revisão |
| Cenários 8/10/12 | Implementados e testados com filtros |
| Comparação mensal | Implementada; exige o mês imediatamente anterior |
| Dashboard e mapa | Implementados; mapa usa malha IBGE, consultas vêm da FastAPI |
| CSV/XLSX | Implementados e testados; proteção contra fórmulas de planilha |
| Qualidade, logs e testes externos | Implementados; resultados de requisições reais persistidos |
| PostgreSQL | Esquema SQLAlchemy e Compose preparados; não executado porque daemon Docker está parado |
| Airflow mensal | DAG preparado, verificação diária idempotente; não executado nem ativado |
| Metabase | Serviço e visões SQL preparados; configuração de dashboard ainda manual |
| Backup | Script preparado; backup/restauração reais não executados |
| Produção | Pendente de servidor Python/PostgreSQL e homologação dos dados |

O painel apresenta dados reais dentro do recorte de classificação, sem alegar cobertura nacional completa. Passaram 71 testes automatizados, 13 GETs reais e 16 consultas concorrentes. Consulte o [relatório completo](Relatorio_Downloads_Testes_e_Atualizacao.md).
