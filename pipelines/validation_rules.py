"""
Rule definitions for the labor validation engine as pure SQL builders.

Kept separate from validation_engine.py (side-effectful script) so unit
tests can exercise rule logic against controlled in-memory fixtures.
Each builder takes a SQL source expression that yields the columns the
rule needs and returns a SELECT with the detection contract columns.
"""


def uc1_query(source: str) -> str:
    """UC1 — HE Progressiva: additional overtime hours (>1h) paid at 50% instead of additional-tier percent."""
    return f"""
    SELECT m.employee_id, m.competence, 1 AS use_case,
           'HE progressiva incorreta' AS rule_name, 'remuneracao' AS category, 'alto' AS severity,
           CAST(m.overtime_70_amount AS VARCHAR) AS detected_value,
           CAST(ROUND(m.overtime_70_hours * m.hourly_rate * (1 + m.he_additional_hours_percent), 2) AS VARCHAR) AS expected_value,
           ROUND(m.overtime_70_hours * m.hourly_rate * (m.he_additional_hours_percent - m.he_first_hour_percent), 2) AS financial_impact,
           CASE WHEN m.he_progressive THEN
               'Horas extras adicionais (>1h) pagas a ' || CAST(m.he_first_hour_percent*100 AS VARCHAR) || '% em vez de '
               || CAST(m.he_additional_hours_percent*100 AS VARCHAR) || '%'
           ELSE 'CCT nao preve HE progressiva, mas ha horas registradas' END AS detail
    FROM ({source}) m
    WHERE m.overtime_70_hours > 0
      AND ABS(m.overtime_70_amount - ROUND(m.overtime_70_hours * m.hourly_rate * (1 + m.he_additional_hours_percent), 2)) > 0.50
      AND m.he_progressive = TRUE
    """


def uc8_query(source: str) -> str:
    """UC8 — Active employee without time-clock records in the period."""
    return f"""
    SELECT m.employee_id, m.competence, 8 AS use_case,
           'Funcionario sem registro de ponto' AS rule_name, 'cadastro' AS category, 'critico' AS severity,
           '0 registros' AS detected_value,
           '>0 registros esperados' AS expected_value,
           0.0 AS financial_impact,
           'Funcionario ativo na folha sem marcacoes de ponto no periodo' AS detail
    FROM ({source}) m
    WHERE m.missing_records > 0
    """


def uc28_query(tr_source: str) -> str:
    """UC28 — Jornada Sobreposta: real interval-overlap between shift spans.

    Uses entry_1/exit_1/entry_2/exit_2 marks per record; a day is flagged
    only when two same-day records have overlapping time spans (strict
    inequality, boundary touch is not overlap). Overlap measured in minutes.
    When day marks are absent the rule cannot assess that record pair —
    this limitation is documented in the detail field.
    """
    return f"""
    WITH spans AS (
        SELECT record_id, employee_id, date_sk, total_hours,
               COALESCE(LEAST(entry_1, entry_2), entry_1, entry_2) AS span_start,
               COALESCE(GREATEST(exit_1, exit_2), exit_1, exit_2) AS span_end,
               CAST(entry_1 AS VARCHAR) AS entry_1_txt, CAST(exit_1 AS VARCHAR) AS exit_1_txt
        FROM ({tr_source})
        WHERE total_hours > 0
    ),
    overlap_pairs AS (
        SELECT a.employee_id, a.date_sk,
               a.record_id, b.record_id AS record_id_2,
               DATEDIFF('minute', GREATEST(a.span_start, b.span_start), LEAST(a.span_end, b.span_end)) AS overlap_minutes,
               a.entry_1_txt, a.exit_1_txt, b.entry_1_txt, b.exit_1_txt
        FROM spans a
        JOIN spans b
          ON a.employee_id = b.employee_id
         AND a.date_sk = b.date_sk
         AND a.record_id < b.record_id
        WHERE a.span_start IS NOT NULL AND b.span_start IS NOT NULL
          AND a.span_end IS NOT NULL AND b.span_end IS NOT NULL
          AND a.span_start < b.span_end
          AND b.span_start < a.span_end
    )
    SELECT o.employee_id, CAST(o.date_sk AS VARCHAR) AS competence, 28 AS use_case,
           'Jornada sobreposta' AS rule_name, 'jornada' AS category, 'medio' AS severity,
           'Sobreposicao de ' || CAST(o.overlap_minutes AS VARCHAR) || ' min (rec ' || o.record_id || ' x rec ' || o.record_id_2 || ')' AS detected_value,
           'Jornada unica por dia' AS expected_value,
           0.0 AS financial_impact,
           'Sobreposicao real de intervalos de jornada: ' || CAST(o.overlap_minutes AS VARCHAR) || ' min entre registros ' || o.record_id
           || ' (' || o.entry_1_txt || '-' || o.exit_1_txt || ') e ' || o.record_id_2 || ' (' || o.entry_1_txt || '-' || o.exit_1_txt || ')'
           || '. Avaliacao limitada aos dias com marcas de entrada/saida legiveis.' AS detail
    FROM overlap_pairs o
    WHERE o.overlap_minutes > 0
    """
