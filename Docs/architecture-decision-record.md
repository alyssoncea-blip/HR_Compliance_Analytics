# Architecture Decision Record (ADR)

## Contexto
Projeto de auditoria trabalhista com dados sintéticos e regras reais de CCT, cobrindo 3 estados com diferenças regulatórias.

## Decisão 1: Stack local com DuckDB + Parquet
- **Escolha:** processamento in-process com DuckDB e camadas Bronze/Silver/Gold em Parquet.
- **Trade-off:** menor custo e alta portabilidade para portfólio vs ausência de cluster distribuído.
- **Limite conhecido:** escala prática limitada para cenários muito acima de dezenas/centenas de milhões de linhas.

## Decisão 2: Motor de validação orientado a regras SQL
- **Escolha:** 32 regras implementadas em SQL/Pandas no `validation_engine.py`.
- **Trade-off:** fácil rastreabilidade e explicabilidade vs custo de manutenção com crescimento de regras.
- **Limite conhecido:** necessidade de framework declarativo para governar centenas de regras.

## Decisão 3: Passivo derivado de inconsistências detectadas
- **Escolha:** `fact_passivo_trabalhista` derivado da `fact_detected_inconsistency`.
- **Trade-off:** causalidade e auditoria fortes vs dependência da qualidade do motor de detecção.
- **Limite conhecido:** estimativa de impacto usa fatores por severidade; requer calibração com dados reais.

## Decisão 4: Temporalidade de CCT versionada
- **Escolha:** dimensão `dim_cct_rule_version` com `valid_from`/`valid_to`.
- **Trade-off:** aderência regulatória histórica vs maior complexidade de joins temporais.
- **Limite conhecido:** versão atual cobre regras principais; expansão para cláusulas específicas ainda pendente.

## Decisão 5: Observabilidade operacional simples
- **Escolha:** trilhas JSON de histórico + SLA + alertas em log local.
- **Trade-off:** implementação rápida e auditável vs ausência de integração nativa com stack de monitoramento corporativa.
- **Limite conhecido:** recomendado evoluir para alertas externos (Slack/Email/PagerDuty) e painéis de SLO.

## Próximas decisões planejadas
- Migrar contratos de dados para framework dedicado (Great Expectations/Soda).
- Externalizar regras CCT para metadados declarativos.
- Incluir orquestração com retries, backfill e monitoramento de DAG.
