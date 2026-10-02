# Importação complementar OpenEV — 10/09/2026

Foi baixado o JSON compilado da versão v1.24.0 (3.175.964 bytes). Dos 1.189 registros do arquivo, 607 informam BR em mercados e foram gravados na tabela candidato_tecnico da base ativa. O arquivo bruto fica em data/raw/openev/v1.24.0.json, com SHA-256 registrado em openev-download.json e transferências em data/transfer-log.jsonl.

A tela Fontes e qualidade possui o botão “Baixar e salvar base técnica OpenEV”, protegido pela mesma chave administrativa. A consulta pública /api/v1/technical-candidates retorna os candidatos persistidos. Reimportar a mesma versão não duplica registros: teste HTTP real confirmou zero inserções na repetição. Escrita sem chave retornou 401. Os 71 testes existentes passaram e o build do frontend passou.

A fonte identifica mercados, mas isso não comprova equivalência com cada versão brasileira da SENATRAN. Todos os 607 registros permanecem PENDENTE_REVISAO. Não foram alterados os totais da frota nem a cobertura de baterias aprovadas. Dados globais de garantia não foram aplicados automaticamente.

A integração consulta metadados da release e baixa o arquivo completo, sem depender da API direta OpenEV. A SENATRAN continua usando o ZIP oficial mensal processado no servidor. O histórico de falhas é preservado e pode ser expandido no painel.

Fonte: https://github.com/open-ev-data/open-ev-data-dataset
