# Casos de Uso — Validação Trabalhista e Regras de CCT

## Caso 1 — Hora Extra Progressiva

A CCT determina:

- primeira hora extra = 50%
- horas adicionais após a primeira = 70%

O sistema deve validar:

- se a folha aplicou corretamente os percentuais,
- se o ponto confirma as horas trabalhadas,
- e se o pagamento bate com a folha.

---

## Caso 2 — Hora Extra em Domingo

A CCT determina:

- trabalho aos domingos = 100%

O sistema deve identificar:

- funcionários que trabalharam no domingo,
- se a folha aplicou o adicional correto,
- e se houve pagamento correspondente.

---

## Caso 3 — Adicional Noturno

A CCT define adicional noturno de 25% entre 22h e 5h.

O sistema deve:

- identificar jornadas noturnas no ponto,
- calcular o adicional esperado,
- comparar com folha e pagamento.

---

## Caso 4 — Banco de Horas Excedido

A CCT permite no máximo 40 horas acumuladas no banco.

O sistema deve:

- calcular saldo acumulado,
- identificar funcionários acima do limite,
- gerar alerta de risco trabalhista.

---

## Caso 5 — Intervalo Intrajornada Não Respeitado

Funcionário trabalhou mais de 6 horas sem intervalo mínimo obrigatório.

O sistema deve:

- identificar ausência/redução de intervalo,
- calcular possível passivo,
- gerar inconsistência crítica.

---

## Caso 6 — Divergência entre Ponto e Folha

O ponto mostra 18 horas extras.
A folha pagou apenas 10.

O sistema deve:

- identificar divergência,
- calcular valor não pago,
- classificar severidade.

---

## Caso 7 — Pagamento Financeiro Divergente

A folha indica pagamento líquido de R$ 4.850.
O comprovante bancário mostra R$ 4.200.

O sistema deve:

- detectar diferença,
- validar se houve pagamento parcial,
- gerar alerta financeiro.

---

## Caso 8 — Funcionário sem Registro de Ponto

Funcionário ativo na folha não possui marcações no período.

O sistema deve:

- identificar ausência total de ponto,
- validar possíveis afastamentos,
- sinalizar inconsistência.

---

## Caso 9 — Funcionário Recebendo após Demissão

Funcionário desligado continua recebendo verbas.

O sistema deve:

- comparar data de demissão,
- validar pagamentos posteriores,
- gerar alerta crítico.

---

## Caso 10 — Cargo com Regra de Hora Extra Diferente

A CCT define:

- Analista = HE 50%
- Supervisor = HE 80%

O sistema deve:

- identificar cargo,
- aplicar regra correta,
- validar cálculo.

---

## Caso 11 — Mudança de Regra entre Anos

CCT 2023:

- HE domingo = 80%

CCT 2024:

- HE domingo = 100%

O sistema deve:

- aplicar regra conforme competência,
- respeitar vigência temporal,
- validar cálculos históricos.

---

## Caso 12 — Jornada 12x36

Funcionário possui escala 12x36.

O sistema deve:

- validar escala permitida,
- detectar jornadas excedidas,
- validar pagamento correto.

---

## Caso 13 — Adicional de Periculosidade

Cargo exige adicional de 30%.

O sistema deve:

- identificar cargos elegíveis,
- validar aplicação do adicional,
- comparar folha e pagamento.

---

## Caso 14 — DSR Calculado Incorretamente

Horas extras impactam DSR.

O sistema deve:

- recalcular DSR esperado,
- validar fórmula aplicada,
- detectar diferenças.

---

## Caso 15 — Feriado Trabalhado sem Adicional

Funcionário trabalhou em feriado.
Folha não aplicou adicional.

O sistema deve:

- identificar feriado,
- validar jornada,
- calcular valor devido.

---

## Caso 16 — Banco de Horas Negativo Indevido

Funcionário ficou com saldo negativo acima do permitido.

O sistema deve:

- validar limite da CCT,
- detectar abuso operacional,
- gerar alerta.

---

## Caso 17 — Funcionário com CPF Divergente

CPF do sistema financeiro diferente do RH.

O sistema deve:

- detectar inconsistência cadastral,
- impedir reconciliação automática,
- classificar risco.

---

## Caso 18 — Evento Pago sem Correspondência

Pagamento de adicional lançado sem evento correspondente na folha.

O sistema deve:

- detectar inconsistência financeira,
- identificar possível erro operacional.

---

## Caso 19 — Funcionário sem Sindicato Definido

Funcionário não possui sindicato associado.

O sistema deve:

- identificar ausência,
- impedir aplicação automática da CCT,
- gerar inconsistência.

---

## Caso 20 — Escala Incompatível com Convenção

CCT permite apenas escala 5x2.
Funcionário está registrado como 6x1.

O sistema deve:

- validar escala permitida,
- gerar risco trabalhista.

---

## Caso 21 — Pagamento Duplicado

Funcionário recebeu duas vezes o mesmo evento.

O sistema deve:

- detectar duplicidade,
- calcular impacto financeiro,
- gerar alerta.

---

## Caso 22 — Hora Extra sem Aprovação

Política exige aprovação acima de 2h extras diárias.

O sistema deve:

- identificar excesso,
- validar aprovação,
- gerar alerta operacional.

---

## Caso 23 — Promoção sem Atualização Salarial

Funcionário mudou de cargo mas salário permaneceu antigo.

O sistema deve:

- comparar histórico,
- validar coerência salarial,
- detectar inconsistência.

---

## Caso 24 — Adicional Noturno Aplicado Fora do Horário

Sistema aplicou adicional antes das 22h.

O sistema deve:

- validar faixa horária,
- recalcular valor correto.

---

## Caso 25 — Funcionário Trabalhando Acima do Limite Legal

Funcionário ultrapassou limite semanal permitido pela CCT.

O sistema deve:

- consolidar jornada semanal,
- calcular excesso,
- gerar risco trabalhista crítico.

---

## Caso 26 — Divergência entre Sindicato e CCT Aplicada

Funcionário pertence ao sindicato A.
Folha aplicou regras da CCT do sindicato B.

O sistema deve:

- validar sindicato correto,
- detectar aplicação incorreta da convenção.

---

## Caso 27 — Falta Descontada Incorretamente

Funcionário apresentou atestado.
Folha realizou desconto mesmo assim.

O sistema deve:

- validar justificativa,
- detectar desconto indevido.

---

## Caso 28 — Funcionário com Jornada Sobreposta

Ponto mostra duas jornadas simultâneas.

O sistema deve:

- detectar sobreposição,
- validar erro de marcação.

---

## Caso 29 — Adicional de Insalubridade Ausente

Cargo exige adicional obrigatório.
Folha não aplicou.

O sistema deve:

- validar elegibilidade,
- calcular impacto financeiro.

---

## Caso 30 — Inconsistência Temporal de CCT

Sistema aplicou regra futura em competência antiga.

O sistema deve:

- validar vigência,
- identificar erro temporal de cálculo.

---

## Caso 31 — Férias Vencidas não Gozadas (Passivo)

Período aquisitivo venceu e férias não foram concedidas.

O sistema deve:

- cruzar período aquisitivo com gozo registrado,
- identificar férias vencidas e não pagas,
- calcular passivo trabalhista (dobro do valor).

---

## Caso 32 — Alerta Preventivo de Vencimento de Férias

Funcionário está próximo do fim do período aquisitivo sem agendamento de férias.

O sistema deve:

- calcular data-limite de concessão (período aquisitivo + 12 meses),
- emitir alerta preventivo para RH com 60, 30 e 15 dias de antecedência,
- listar funcionários por grau de urgência (crítico: < 15 dias).
