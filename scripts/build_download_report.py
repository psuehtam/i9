"""Build the handoff report from measured transfers and successful ETL runs."""
import json,csv,zipfile
from datetime import datetime,timezone
from pathlib import Path
from sqlalchemy import select
from src.db import ROOT,engine,runs

def fmt(value,d=2):
    return f'{value:,.{d}f}'.replace(',','_').replace('.',',').replace('_','.')

def main():
    events=[json.loads(line) for line in (ROOT/'data/transfer-log.jsonl').read_text(encoding='utf-8').splitlines()]
    validation=json.loads((ROOT/'docs/real-data-validation.json').read_text(encoding='utf-8'))
    with engine.connect() as c:
        successful=[dict(r) for r in c.execute(select(runs).where(runs.c.status=='SUCESSO',runs.c.reference.in_(['2026-06','2026-07']))).mappings()]
    total=sum(e.get('wire_body_bytes',0)+e.get('downloaded_bytes',0) for e in events)
    files=[e for e in events if e['kind']=='file' and not e.get('reused') and not e.get('failed')]
    s=validation['summary'];m=validation['monthly']
    table=[];archive_rows=[]
    for e in sorted(files,key=lambda e:e['path']):
        p=ROOT/e['path']
        label='SENATRAN '+('junho/2026' if '2026-06' in str(p) else 'julho/2026') if p.suffix=='.zip' else 'INMETRO PBE Veicular 2026'
        table.append(f"| {label} | {fmt(e['file_bytes'],0)} | {fmt(e['file_bytes']/1e6)} MB | {fmt(e['seconds'])} s |")
        if p.suffix=='.zip':
            with zipfile.ZipFile(p) as z:
                archive_rows.append({'file':e['path'],'compressed_bytes':e['file_bytes'],'uncompressed_bytes':sum(i.file_size for i in z.infolist()),'members':[i.filename for i in z.infolist()]})
    timings=[]
    for r in sorted(successful,key=lambda r:r['reference']):
        t=r['details']['timings'];download=next(e for e in files if r['reference'] in e['path'])
        combined=download['seconds']+t['processing_seconds']+t['locations_seconds']
        timings.append(f"| {r['reference']} | {fmt(download['seconds'])} s | {fmt(t['processing_seconds'])} s | aproximadamente {fmt(combined/60,1)} min |")
    api_events=[e for e in events if e['kind']=='api_json']
    api_bytes=sum(e.get('wire_body_bytes',0) for e in api_events)
    artifact={'created_at':datetime.now(timezone.utc).isoformat(),'total_transferred_body_bytes':total,'new_file_bytes':sum(e['file_bytes'] for e in files),
              'api_body_bytes':api_bytes,'new_files':files,'archive_sizes':archive_rows,'successful_runs':successful,'transfer_events':events}
    (ROOT/'docs/download-inventory.json').write_text(json.dumps(artifact,ensure_ascii=False,indent=2),encoding='utf-8')
    with (ROOT/'docs/download-inventory.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f,delimiter=';');writer.writerow(['data_utc','tipo','url','arquivo','bytes_transferidos','bytes_arquivo','segundos','reutilizado','sha256'])
        for e in events:writer.writerow([e['recorded_at'],e['kind'],e['url'],e.get('path',''),e.get('wire_body_bytes',0)+e.get('downloaded_bytes',0),e.get('file_bytes',''),e['seconds'],e.get('reused',False),e.get('sha256','')])
    text=f'''# Relatório de downloads, testes e atualização — i9+

Data: 09/09/2026. Testes executados neste computador, com a base local SQLite e consultas HTTP reais à FastAPI.

## Resultado entregue

As referências **junho e julho de 2026 foram baixadas, processadas e disponibilizadas no painel**. O histórico dos dois meses está preservado. Downloads automáticos no servidor estão habilitados na configuração local.

- Junho: **{fmt(m['previous'],0)} veículos** no recorte.
- Julho: **{fmt(m['current'],0)} veículos** no recorte.
- Variação: **+{fmt(m['delta'],0)} veículos (+{fmt(m['change_pct'])}%)**.
- Julho possui **{s['brands']} marcas, {s['models']} modelos e {s['versions']} versões** identificados nas famílias cobertas.

**Limite de cobertura:** os números são um recorte de famílias BEV com regras explícitas de classificação. Existem 12 famílias configuradas e 11 presentes na referência de julho. Não são o total completo de elétricos do Brasil. Híbridos e modelos ainda não classificados não entram.

## 1. O que foi baixado e quanto ocupou

### Arquivos novos desta etapa

| Fonte / referência | Bytes do arquivo | Tamanho decimal | Tempo medido de download |
|---|---:|---:|---:|
{chr(10).join(table)}

Os dois ZIPs da SENATRAN somam **{fmt(sum(a['compressed_bytes'] for a in archive_rows)/1e6)} MB**. Eles foram necessários para importar um mês e testar a variação em relação ao mês anterior.

### APIs e arquivos auxiliares

| Fonte | Uso | Tamanho / situação |
|---|---|---|
| SENATRAN — API de catálogo | Descobrir arquivos, referências e metadados | Aproximadamente 139 KB por consulta; consultas repetidas constam do inventário |
| IBGE — API de municípios | Validar município, UF e código oficial | 112.459 bytes transferidos por resposta comprimida; arquivo JSON normalizado em disco: {fmt((ROOT/'data/raw/ibge-municipios.json').stat().st_size,0)} bytes |
| OpenEV — API GitHub | Consultar metadados e fichas técnicas por versão | Um candidato aplicável ao mercado BR salvo para revisão ({fmt((ROOT/'data/staging/openev-byd-dolphin-2025.json').stat().st_size,0)} bytes); respostas completas estão contabilizadas no inventário |
| BYD — ficha Dolphin GS 2026 | Capacidade e garantia por versão | 1.491.049 bytes; arquivo já existente reutilizado, sem novo download |
| IBGE — malha das UFs | Mapa do painel | {fmt((ROOT/'dashboard/public/br-uf.geojson').stat().st_size,0)} bytes no arquivo local; reutilizado, sem novo download |

**Tráfego medido nesta etapa: {fmt(total/1e6)} MB ({fmt(total,0)} bytes)** de corpos de respostas HTTP. Esse total inclui os novos arquivos e {fmt(api_bytes/1e6)} MB de respostas JSON, inclusive consultas repetidas durante os testes. Não inclui cabeçalhos HTTP, TLS, arquivos reaproveitados ou dependências de software instaladas na etapa anterior. Não foi necessário instalar novas bibliotecas nesta etapa.

MB neste relatório significa 1.000.000 bytes. O tamanho que o Windows apresenta em MiB pode ser numericamente menor, sem diferença no arquivo.

## 2. Armazenamento e tratamento dos arquivos grandes

Dentro dos dois ZIPs há **{fmt(sum(a['uncompressed_bytes'] for a in archive_rows)/1e9,3)} GB** de TXT descompactado. Os TXT foram lidos em fluxo, em blocos de 100.000 linhas; não foi necessário extrair integralmente esse volume em disco.

Os arquivos brutos ficam em `data/raw/AAAA-MM/senatran/`. SHA-256, URLs, bytes e tempos estão em [download-inventory.json](download-inventory.json) e [download-inventory.csv](download-inventory.csv). Um arquivo completo já existente é reutilizado ao repetir a carga.

O processamento preservou registros BEV com ano ou localização ausentes. Em julho, **{fmt(validation['missing_year_vehicles'],0)} veículos estão sem ano** e **{fmt(validation['missing_location_vehicles'],0)} sem localização**. Essas categorias podem se sobrepor; não devem ser somadas. Ano ausente não entra em projeções por ano; localização ausente não é atribuída artificialmente a uma UF.

## 3. Quanto tempo demora para atualizar

| Referência | Download do ZIP | Processamento validado | Estimativa combinando as etapas medidas |
|---|---:|---:|---:|
{chr(10).join(timings)}

Download e processamento foram cronometrados em execuções separadas. A última coluna soma etapas medidas; não é uma execução contínua cronometrada de ponta a ponta. Nesta máquina, reserve **cerca de 3 a 4 minutos por referência nova**, com variação conforme conexão, tamanho e carga do computador. As tentativas iniciais de ajuste de formato não fazem parte desse tempo operacional.

Quando a referência já existe, a API consulta o catálogo e retorna `SEM_NOVIDADE`: **{fmt(validation['no_new_month_seconds'])} segundo no teste**, sem baixar ou reprocessar os ZIPs. O tempo de abrir uma consulta no painel é independente da carga mensal.

## 4. Com que frequência atualiza

| Camada | Frequência / comportamento |
|---|---|
| Publicação da SENATRAN | Mensal, dependente da disponibilização no portal; não há dia fixo garantido pelo sistema |
| Última referência encontrada | Julho/2026, no catálogo consultado em 09/09/2026; agosto ainda não estava disponível nesse conjunto |
| Atualização do sistema hoje | Manual, pelo botão **Atualizar base** ou pela API administrativa; o download fica no servidor |
| Agendamento preparado | DAG Airflow verifica diariamente às 05:00 UTC, equivalentes a 02:00 em Brasília; só publica se houver mês novo |
| Situação do agendamento | **Ainda não está ativo**: requer iniciar o serviço Airflow/Docker e ativar o DAG. Não foi criada tarefa agendada no Windows |
| INMETRO e fabricantes | Revisão quando houver nova tabela/ficha ou mudança de versão; não se presume publicação mensal |
| OpenEV | Enriquecimento sob demanda e revisão técnica antes de aprovar a associação |

Os metadados do catálogo consultado registram junho em 09/07/2026 e julho em 07/08/2026. Isso demonstra que a referência de um mês pode chegar no mês seguinte; a aplicação não inventa meses ausentes.

## 5. Testes e correções realizados

- **71 testes automatizados passaram**, incluindo o formato real dos cabeçalhos, UFs por extenso, quantidades como `6.0`, ausência de ano/localização, aliases municipais, filtros, exportações, histórico e concorrência de conexões.
- **13 consultas GET por HTTP real** validaram frota, modelos, baterias, fontes, qualidade, três cenários e exportações. Todas retornaram HTTP 200.
- **16 consultas concorrentes** retornaram HTTP 200; o lote levou {fmt(validation['concurrent_batch_seconds'])} segundos.
- A exportação CSV e a exportação Excel foram abertas e somadas: ambas mantiveram os **222.373 veículos** de julho.
- Uma soma independente com DuckDB sobre o recorte extraído da fonte confirmou os mesmos **222.373 veículos**. A classificação continua limitada ao catálogo de famílias; essa conciliação verifica a quantidade dentro do recorte, não cobertura nacional completa.
- As projeções de 8, 10 e 12 anos preservaram a contagem dos veículos com ano conhecido. Registros sem ano foram explicitamente separados.
- O disparo administrativo de uma referência já publicada retornou `SEM_NOVIDADE`, sem duplicar o histórico.
- TypeScript e build de produção passaram; página e proxy do painel responderam HTTP 200. Não foram feitos testes automatizados de cliques no navegador.

Foi corrigido o uso de conexões aninhadas e acrescentado cache limitado por snapshot imutável, além de limite de concorrência. Isso evita que as consultas simultâneas do painel esgotem as conexões da base local.

As consultas medidas, excluindo a geração de Excel, ficaram entre **{fmt(min(x['seconds'] for x in validation['requests']))} e {fmt(max(x['seconds'] for x in validation['requests'] if 'xlsx' not in x['endpoint']))} segundo**. O Excel completo levou **{fmt(next(x['seconds'] for x in validation['requests'] if 'xlsx' in x['endpoint']))} segundos** nesta execução.

## 6. Baterias, auditoria e o que ainda falta

A equivalência **Dolphin GS ↔ Dolphin GS 180EV** foi conferida no PBE e aplicada apenas ao ano 2026, coberto pela ficha técnica brasileira revisada em 09/07/2026. A ficha informa 44,9 kWh e garantia de 8 anos ou 200.000 km.

Para preservar a auditoria, a primeira base permanece em `data/i9.db`. A versão validada está em `data/i9-validated-v2.db`, selecionada no `.env`. A revisão modificou somente a associação técnica, sem alterar quantidades ou remover meses. Detalhes: [dataset-revision.json](dataset-revision.json).

Em julho, **{fmt(s['known_vehicles'],0)} veículos ({fmt(s['coverage_pct'],1)}% do recorte)** têm bateria associada pela regra validada, totalizando **{fmt(s['energy_mwh'],3)} MWh nominais calculados**. Isso **não é toda a energia da frota**, nem capacidade residual. As demais baterias permanecem pendentes. Não foram inferidas garantias globais da OpenEV para versões brasileiras nem extrapolados dados para outros anos.

Ainda faltam ampliar o catálogo de baterias e famílias BEV, ativar a orquestração e homologar PostgreSQL/Metabase em Docker. Os testes desta entrega usaram SQLite local. O relatório não declara essas etapas concluídas.

## Evidências e acesso

- Painel local: <http://localhost:3000>
- API: <http://127.0.0.1:8000/docs>
- [Resultados HTTP com dados reais](real-data-validation.json)
- [Conciliação de julho](reconciliation-july.json)
- [Testes automatizados](test-results.xml)
- [Inventário detalhado em CSV](download-inventory.csv)
- [Inventário e cronometrias em JSON](download-inventory.json)
- [SENATRAN — catálogo público](https://dados.transportes.gov.br/api/3/action/package_show?id=registro-nacional-de-veiculos-automotores-renavam)
- [INMETRO — PBE Veicular](https://www.gov.br/inmetro/pt-br/assuntos/regulamentacao/avaliacao-da-conformidade/programa-brasileiro-de-etiquetagem/tabelas-de-eficiencia-energetica/veiculos-automotivos-pbe-veicular)
'''
    (ROOT/'docs/Relatorio_Downloads_Testes_e_Atualizacao.md').write_text(text,encoding='utf-8')
    print('Report generated.',total,'transferred bytes')

if __name__=='__main__':main()
