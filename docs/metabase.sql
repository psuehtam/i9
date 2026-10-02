-- PostgreSQL views for optional Metabase exploration. Historical battery rows
-- are immutable: specifications are added with a new ID, not overwritten.
CREATE OR REPLACE VIEW vw_frota_bateria AS
SELECT f.reference AS referencia,l.uf,l.city AS municipio,f.brand AS marca,
 f.model AS modelo,f.version AS versao,f.vehicle_year AS ano_veiculo,f.quantity AS veiculos,
 b.capacity_kwh AS capacidade_kwh,b.chemistry AS quimica,f.confidence AS confianca,
 CASE WHEN f.confidence IN ('A','B') THEN f.quantity*b.capacity_kwh/1000 END AS energia_mwh,
 CASE WHEN f.confidence IN ('A','B') THEN f.vehicle_year+b.warranty_years END AS fim_garantia_estimado,
 b.warranty_km AS limite_garantia_km, f.source_id AS fonte,b.provenance AS origem_bateria
FROM frota_snapshot f JOIN localidade l ON l.id=f.location_id LEFT JOIN bateria b ON b.id=f.battery_id;

CREATE OR REPLACE VIEW vw_janelas_bateria AS
SELECT v.*,s.anos AS cenario_anos,v.ano_veiculo+s.anos AS ano_janela_estimada
FROM vw_frota_bateria v CROSS JOIN (VALUES (8),(10),(12)) AS s(anos);
