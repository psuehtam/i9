# Integração de dados individuais de baterias

O NEXUS aceita registros pelo OpenAPI em `/docs`, nas operações `POST /api/v3/battery-import/validate` e `POST /api/v3/battery-import/records`. Use `X-API-Key` de uma conta `data_engineer` configurada em `I9_ROLE_TOKENS` ou a chave administrativa em `X-Admin-Key`. Envie sempre HTTPS como fonte e um `source_record_id` estável da origem.

## Exemplo JSON

```json
{
  "source_url": "https://parceiro.example/relatorios/bateria-001",
  "source_record_id": "medicao-bateria-001-v1",
  "vehicle_code": "VEI-EXEMPLO-000001",
  "vin": "1HGBH41JXMN109186",
  "state": "PR",
  "municipality": "Curitiba",
  "battery_manufacturer": "Fabricante Exemplo",
  "battery_serial": "PACK-001",
  "installed_at": "2026-01-01",
  "passport": {
    "11": {"value": "44.9 kWh", "status": "confirmed", "source": "https://parceiro.example/ficha"},
    "12": {"value": "LFP", "status": "confirmed", "source": "https://parceiro.example/ficha"},
    "42": {"value": null, "status": "not_applicable", "source": "https://parceiro.example/ficha", "reason": "Bateria não colocada no mercado da UE"}
  },
  "measurements": [
    {"observed_at": "2026-09-01T12:00:00Z", "soh_percent": 79.0, "cycle_count": 800}
  ]
}
```

`vehicle_code` precisa ser um código de veículo já cadastrado. O chassi (`vin`) deve corresponder ao veículo ou estar disponível para verificá-lo. O NEXUS não liga baterias a veículos por semelhança de marca ou modelo. O serial identifica a bateria física; um serial já vinculado a outro veículo é rejeitado. A fonte e os campos do passaporte permanecem no histórico de revisões. Medições devem trazer horário e fuso; a mais recente determina a saúde exibida no dashboard.

Envie o mesmo JSON para `/validate` antes de `/records`. A validação não grava nada. Repetir o mesmo `source_url` + `source_record_id` + conteúdo devolve o mesmo resultado sem criar duplicatas. Para corrigir informação, envie um novo `source_record_id`, por exemplo `medicao-bateria-001-v2`; uma medição com a mesma data de outra já gravada exige revisão explícita. Os 71 identificadores de campos e suas descrições estão na resposta da ficha da bateria e no esquema de `src/battery_passport.py`. Campos reais ausentes permanecem pendentes; a integração não os inventa.

O modo fictício da Administração é independente desta API. Os perfis simulados são gerados em leitura e nunca são enviados a `/records`.
