# Evolução I9+ — entrega local de 14/09/2026

O painel principal está em http://localhost:3000 e a consulta mensal anterior foi preservada em http://localhost:3000/frota. A API v2 e seus contratos estão disponíveis em http://127.0.0.1:8000/docs.

## Implementação

| Pedido do plano | Entrega |
|---|---|
| Separar mercado, especificações e ativos | Tabelas distintas de observações agregadas, especificações, modelos de bateria, veículos, baterias físicas e instalações |
| Múltiplas fontes e rastreabilidade | Snapshots, URL original, hash, período, escopo, transformação e comparação de versões |
| Eletrificados e ônibus | Taxonomia BEV, PHEV, HEV, HEV Flex e MHEV; dados ABVE separados do recorte SENATRAN |
| Cadastro individual | Identificação restrita, histórico de instalações, várias posições de packs por veículo e desvinculação com data |
| Evidência de bateria | Candidatos, revisão, aprovação e publicação em snapshot derivado sem alterar o original |
| Vida útil e passaporte | Campos de SOH, SOCE, ciclos, energia processada, identificação e histórico; validação de valores e contadores |
| Disponibilidade futura | Cenários configuráveis de idade, energia nominal conhecida e capacidade residual opcional |
| Mapa de oportunidades | Recorte geográfico, cobertura técnica, janela de idade e exportação com premissas |
| Qualidade | Indicador de completude e pendências; não representa probabilidade de acerto |
| Ingestão | API interna, arquivos CSV/XLSX/JSON, fontes públicas revisadas e sincronização do processamento SENATRAN |
| Controle de acesso | Papéis por chave, restrição de identificadores e auditoria das alterações |

## Dados presentes

- SENATRAN: 205.816 veículos em junho e 222.373 em julho de 2026 no recorte de famílias eletrificadas então classificadas. Não é o total nacional nem o acumulado ABVE. Junho/julho não ganham linhas novas; catálogo ampliado vale no próximo ETL.
- ABVE: 950.183 eletrificados leves acumulados até agosto — camada de **mercado**. Escopo e período impedem comparação direta. Meta da Frota = SENATRAN por combustível (~888 mil em fev/2026), por propulsão.
- Energia: BEV, PHEV e HEV não se somam num MWh único sem rótulo. Fichas colam por família+ano quando a regra é única; OpenEV não auto-aprova.
- Ônibus: 589 emplacamentos no primeiro semestre de 2026, em 12 grupos municipais. Brasília possui 90.
- Foram criados 90 registros internos derivados do agregado de Brasília. Eles não são veículos identificados: não têm VIN, placa ou bateria física inventados e não aumentam a quantidade oficial.
- Catálogo: 607 candidatos OpenEV, ficha BYD existente e fichas GWM/Mercedes adicionadas. Candidatos não entram automaticamente no cálculo de energia.
- Energia conhecida de julho permanece 826,0253 MWh, correspondente à regra revisada BYD Dolphin GS 2026. Outros dados técnicos não foram extrapolados para veículos sem correspondência.
- Mercedes eO500U: 98 kWh por pack, configurações de três a seis packs. Não se atribuiu 98 kWh como capacidade de um ônibus inteiro ou aos 589 ônibus ABVE.

## Fontes, arquivos e atualização

Tamanhos abaixo são bytes dos arquivos armazenados, não estimativa do tráfego total de todas as requisições.

| Arquivo/fonte | Bytes | Atualização |
|---|---:|---|
| SENATRAN junho, ZIP | 135.347.542 | Publicação mensal; descoberta diária |
| SENATRAN julho, ZIP | 135.907.513 | Publicação mensal; descoberta diária |
| INMETRO PBE 2026, PDF | 3.387.564 | Conforme revisão oficial; revisão técnica necessária |
| OpenEV v1.24.0, JSON | 3.175.964 | Conforme releases; importação e revisão técnica |
| ABVE mercado agosto, HTML | 143.781 | Artigo mensal revisado; não há conector genérico do BI |
| ABVE ônibus primeiro semestre, HTML | 137.158 | Publicação semestral revisada |
| GWM H6 PHEV34 2025, PDF | 5.085.475 | Conforme ficha do fabricante |
| Mercedes eO500U, HTML | 97.562 | Conforme ficha do fabricante |

Links originais também aparecem em **Saúde das fontes**, com os metadados do snapshot:

- [SENATRAN / catálogo RENAVAM](https://dados.transportes.gov.br/dataset/12686da0-3d71-4499-b432-d270f785c907)
- [ABVE mercado agosto](https://abve.org.br/com-57-mil-emplacamentos-em-agosto-eletrificados-abrem-a-corrida-para-o-milhao-em-setembro/)
- [ABVE ônibus](https://abve.org.br/onibus-eletricos-tem-crescimento-de-925-no-1o-semestre-de-2026-comparado-a-2025/)
- [GWM ficha H6 PHEV34 2025](https://www.gwmmotors.com.br/content/dam/gwm/pages/br/pt/models/haval-h6-phev-34-2025/FichaTecnica_Haval_H6_PHEV34_2025.pdf)
- [Mercedes baterias eO500U](https://www.mercedes-benz-trucks.com.br/onibus/eletrico/tecnologia/bateria)

URLs exatas dos ZIPs, tempos medidos anteriormente e hashes estão em `download-inventory.json` e no relatório de downloads anterior. Os novos downloads ABVE/OEM não têm duração individual registrada; não foi estimado um tempo como se tivesse sido medido.

O agendador local SENATRAN está habilitado: verifica diariamente às 02:00 de Brasília, ou ao abrir a API depois desse horário. A verificação de 14/09 terminou com sucesso. Exige computador e API ligados; não é serviço do Windows. A execução diária é registrada para evitar duplicação após reiniciar. Use **Atualizar base** em `/frota`, na aba **Fontes e qualidade**, para atualização manual. Referência já publicada não é baixada e publicada novamente. Se futuramente usar Airflow, desative o agendador local para evitar dois agendamentos.

## Operação e acesso

Use `scripts/start.ps1` para iniciar. A chave `ADMIN_API_KEY` do `.env` habilita a administração na sessão do painel. Não publique a chave. Papéis opcionais são configurados em `I9_ROLE_TOKENS` como uma lista JSON de objetos com `name`, `role` e `key`; use chaves longas e exclusivas. Não existe SSO implantado. O papel parceiro permanece limitado aos dados públicos até haver contrato e política de acesso apropriados.

Para importar dados próprios, cadastre a fonte e use **Cadastros e importação**, com os modelos CSV/JSON fornecidos. Cadastros individuais e consultas por identificador exigem autorização; arquivos agregados não aceitam VIN. Na revisão de evidências, aprove a associação exata e publique uma versão derivada para manter o histórico.

## Validação e limites

TypeScript e build de produção passaram. 86 testes automatizados passaram, incluindo autorização, isolamento de fontes privadas, idempotência, limites de materialização, instalações de múltiplos packs, histórico de vida útil, cenários e agendador. A validação HTTP real verificou 12 consultas e uma simulação POST, preservando quantidades e bloqueando consultas individuais sem chave. Resultados em `test-results-v2.xml` e `intelligence-live-validation.json`.

O banco anterior foi preservado e existe backup em `data/backups/before-intelligence-20260914-090335.db`. A evolução usa tabelas adicionais no banco ativo.

VIN/RENAVAM, telemetria, contratos de acesso, garantia individual e estado físico das baterias dependem de dados autorizados ainda não fornecidos. As janelas são cenários de baixa confiança, não modelos treinados ou datas previstas de falha. Os campos de passaporte não constituem certificação regulatória. PostgreSQL, Airflow, Metabase e publicação em produção não foram homologados nesta entrega local. O plano está implementado como estrutura e fluxos operacionais; completar a cobertura e calibrar previsões exige essas fontes externas.
