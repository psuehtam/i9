# Evidências de validação

- **71 testes automatizados passaram**, incluindo API, filtros, exportações, histórico, formato real da fonte, ausência de ano/localização e conexões. Evidência: [test-results.xml](test-results.xml).
- **Junho e julho de 2026 processados:** 205.816 e 222.373 veículos no recorte. São 12 famílias configuradas e 11 presentes em julho, sem cobertura nacional completa.
- **13 GETs reais e 16 consultas concorrentes retornaram HTTP 200.** CSV e Excel somam 222.373 veículos. Atualização repetida retornou `SEM_NOVIDADE` em 0,84 segundo, sem baixar novamente os ZIPs. Evidência: [real-data-validation.json](real-data-validation.json).
- **Conciliação independente:** a soma do recorte extraído confirma a quantidade publicada. Evidência: [reconciliation-july.json](reconciliation-july.json).
- **Baterias:** associação técnica validada cobre 18.397 veículos de julho (8,3%). A primeira base está preservada; a base ativa é `data/i9-validated-v2.db`. Evidência: [dataset-revision.json](dataset-revision.json).
- **Frontend:** TypeScript e build passaram; página e proxy responderam 200. Sem testes automatizados de cliques no navegador.
- **Infraestrutura:** Compose validado sintaticamente. PostgreSQL, Metabase, Airflow e restauração de backup ainda não foram exercitados. O agendamento não está ativo; atualização manual.

Tamanhos, tempos, fontes e limites estão no [relatório completo](Relatorio_Downloads_Testes_e_Atualizacao.md).
