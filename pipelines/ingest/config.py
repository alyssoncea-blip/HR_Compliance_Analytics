from dataclasses import dataclass, field
from typing import List
from datetime import date

# ---------------------------------------------------------------------------
# CCT Rules per Union
# ---------------------------------------------------------------------------

@dataclass
class CCTRules:
    union_name: str
    state: str
    company: str
    year_start: int
    year_end: int
    standard_weekly_hours: int
    he_weekday_percent: float
    he_sunday_percent: float
    he_holiday_percent: float
    he_progressive: bool
    he_first_hour_percent: float
    he_additional_hours_percent: float
    night_shift_percent: float
    night_shift_start: int
    night_shift_end: int
    periculosidade_percent: float
    insalubridade_percent: float
    max_hour_bank_hours: float
    min_rest_interval_hours: float
    salary_adjustment_percent: float
    base_salary_min: float
    meal_voucher_amount: float
    food_basket_amount: float
    plr_amount: float


CCT_RULES: List[CCTRules] = [
    CCTRules(
        union_name="Sindágua-MG",
        state="MG", company="Copasa",
        year_start=2024, year_end=2025,
        standard_weekly_hours=44,
        he_weekday_percent=0.50, he_sunday_percent=1.00, he_holiday_percent=1.00,
        he_progressive=True, he_first_hour_percent=0.50, he_additional_hours_percent=0.70,
        night_shift_percent=0.20, night_shift_start=22, night_shift_end=5,
        periculosidade_percent=0.30, insalubridade_percent=0.40,
        max_hour_bank_hours=40.0, min_rest_interval_hours=1.0,
        salary_adjustment_percent=0.0462, base_salary_min=1512.00,
        meal_voucher_amount=450.0, food_basket_amount=180.0, plr_amount=3200.0,
    ),
    CCTRules(
        union_name="Sindágua-RJ",
        state="RJ", company="Águas do Rio",
        year_start=2024, year_end=2025,
        standard_weekly_hours=44,
        he_weekday_percent=0.50, he_sunday_percent=1.00, he_holiday_percent=1.00,
        he_progressive=True, he_first_hour_percent=0.50, he_additional_hours_percent=0.70,
        night_shift_percent=0.20, night_shift_start=22, night_shift_end=5,
        periculosidade_percent=0.30, insalubridade_percent=0.40,
        max_hour_bank_hours=40.0, min_rest_interval_hours=1.0,
        salary_adjustment_percent=0.0520, base_salary_min=1458.00,
        meal_voucher_amount=400.0, food_basket_amount=160.0, plr_amount=2800.0,
    ),
    CCTRules(
        union_name="Sindágua-RN",
        state="RN", company="CAERN",
        year_start=2024, year_end=2025,
        standard_weekly_hours=30,
        he_weekday_percent=0.50, he_sunday_percent=1.00, he_holiday_percent=1.00,
        he_progressive=True, he_first_hour_percent=0.50, he_additional_hours_percent=0.70,
        night_shift_percent=0.20, night_shift_start=22, night_shift_end=5,
        periculosidade_percent=0.30, insalubridade_percent=0.40,
        max_hour_bank_hours=40.0, min_rest_interval_hours=1.0,
        salary_adjustment_percent=0.1270, base_salary_min=1600.00,
        meal_voucher_amount=480.0, food_basket_amount=200.0, plr_amount=3500.0,
    ),
]

# ---------------------------------------------------------------------------
# Volume & Distribution
# ---------------------------------------------------------------------------

SEED = 42
PERIOD_START = date(2024, 1, 1)
PERIOD_END = date(2025, 12, 31)

EMPLOYEES_PER_STATE = {
    "MG": 4000,
    "RJ": 4000,
    "RN": 2000,
}

HIRE_DATE_START = date(2005, 1, 1)
HIRE_DATE_END = date(2024, 12, 31)

# ---------------------------------------------------------------------------
# Position definitions (cargos)
# ---------------------------------------------------------------------------

@dataclass
class PositionDef:
    name: str
    level: str
    min_salary: float
    max_salary: float
    periculosidade: bool
    insalubridade: bool
    requires_approval: bool


POSITIONS: List[PositionDef] = [
    PositionDef("Auxiliar de Serviços Operacionais", "operational", 1512, 1900, True, True, False),
    PositionDef("Auxiliar Administrativo", "administrative", 1512, 2200, False, False, False),
    PositionDef("Operador de Estação de Tratamento I", "operational", 1900, 2500, True, True, False),
    PositionDef("Operador de Estação de Tratamento II", "operational", 2500, 3200, True, True, False),
    PositionDef("Operador de ETA Sênior", "operational", 3200, 4200, True, True, False),
    PositionDef("Bombeiro Hidráulico", "operational", 1800, 2600, True, True, False),
    PositionDef("Eletricista", "technical", 2800, 4000, True, True, False),
    PositionDef("Eletromecânico", "technical", 3200, 4800, True, True, False),
    PositionDef("Técnico de Saneamento", "technical", 2800, 4200, True, False, False),
    PositionDef("Técnico de Segurança do Trabalho", "technical", 3200, 4800, False, False, False),
    PositionDef("Técnico em Informática", "technical", 2800, 4000, False, False, False),
    PositionDef("Analista de RH", "administrative", 3800, 5800, False, False, False),
    PositionDef("Analista de Departamento Pessoal", "administrative", 3500, 5200, False, False, False),
    PositionDef("Analista Contábil", "administrative", 4000, 6000, False, False, False),
    PositionDef("Analista Financeiro", "administrative", 4000, 6000, False, False, False),
    PositionDef("Analista de TI", "technical", 4200, 6500, False, False, False),
    PositionDef("Analista Jurídico", "administrative", 5000, 8000, False, False, False),
    PositionDef("Analista de Compras", "administrative", 3800, 5500, False, False, False),
    PositionDef("Analista de Qualidade", "technical", 3800, 5500, False, False, False),
    PositionDef("Assistente Social", "administrative", 3500, 5200, False, False, False),
    PositionDef("Encarregado de Manutenção", "supervisor", 4500, 6200, True, False, True),
    PositionDef("Encarregado Operacional", "supervisor", 4500, 6200, True, False, True),
    PositionDef("Supervisor Operacional", "supervisor", 5000, 7200, False, False, True),
    PositionDef("Supervisor Administrativo", "supervisor", 5200, 7500, False, False, True),
    PositionDef("Supervisor de RH", "supervisor", 5500, 8000, False, False, True),
    PositionDef("Coordenador de RH", "management", 7000, 10000, False, False, True),
    PositionDef("Coordenador Operacional", "management", 7500, 11000, False, False, True),
    PositionDef("Coordenador Administrativo", "management", 7500, 11000, False, False, True),
    PositionDef("Coordenador de TI", "management", 8000, 12000, False, False, True),
    PositionDef("Gerente de Operações", "management", 12000, 18000, False, False, True),
    PositionDef("Gerente de RH", "management", 13000, 20000, False, False, True),
    PositionDef("Gerente Administrativo", "management", 13000, 20000, False, False, True),
    PositionDef("Gerente de TI", "management", 14000, 22000, False, False, True),
    PositionDef("Diretor de Operações", "management", 22000, 35000, False, False, True),
    PositionDef("Diretor Administrativo", "management", 22000, 35000, False, False, True),
]

# ---------------------------------------------------------------------------
# Units (unidades operacionais)
# ---------------------------------------------------------------------------

@dataclass
class UnitDef:
    name: str
    state: str
    city: str
    unit_type: str


UNITS: List[UnitDef] = [
    # MG - Copasa
    UnitDef("Sede Copasa BH", "MG", "Belo Horizonte", "administrative"),
    UnitDef("Estação de Tratamento Morro Vermelho", "MG", "Nova Lima", "operational"),
    UnitDef("Unidade Regional Copasa Sul", "MG", "Varginha", "mixed"),
    UnitDef("Unidade Regional Copasa Triângulo", "MG", "Uberlândia", "mixed"),
    UnitDef("Unidade Regional Copasa Centro", "MG", "Belo Horizonte", "mixed"),
    UnitDef("Unidade Regional Copasa Leste", "MG", "Governador Valadares", "mixed"),
    UnitDef("Unidade Regional Copasa Norte", "MG", "Montes Claros", "mixed"),
    UnitDef("Estação de Tratamento Rio Manso", "MG", "Rio Manso", "operational"),
    UnitDef("Estação de Tratamento Serra Azul", "MG", "Mateus Leme", "operational"),
    UnitDef("Laboratório Central Copasa", "MG", "Belo Horizonte", "operational"),
    # RJ - Águas do Rio
    UnitDef("Sede Águas do Rio Niterói", "RJ", "Niterói", "administrative"),
    UnitDef("Estação de Tratamento Guandu", "RJ", "Nova Iguaçu", "operational"),
    UnitDef("Unidade Rio Norte", "RJ", "Duque de Caxias", "mixed"),
    UnitDef("Unidade Rio Sul", "RJ", "Rio de Janeiro", "mixed"),
    UnitDef("Unidade Rio Oeste", "RJ", "Campo Grande", "mixed"),
    UnitDef("Unidade Rio Leste", "RJ", "São Gonçalo", "mixed"),
    UnitDef("Unidade Rio Centro", "RJ", "Petrópolis", "mixed"),
    UnitDef("Estação de Tratamento Laranjal", "RJ", "Niterói", "operational"),
    UnitDef("Estação de Tratamento Alcântara", "RJ", "São Gonçalo", "operational"),
    UnitDef("Laboratório Rio", "RJ", "Rio de Janeiro", "operational"),
    # RN - CAERN
    UnitDef("Sede CAERN Natal", "RN", "Natal", "administrative"),
    UnitDef("Estação de Tratamento ETA Norte", "RN", "Natal", "operational"),
    UnitDef("Unidade Regional Mossoró", "RN", "Mossoró", "mixed"),
    UnitDef("Unidade Regional Seridó", "RN", "Caicó", "mixed"),
    UnitDef("Unidade Regional Agreste", "RN", "Nova Cruz", "mixed"),
    UnitDef("Unidade Regional Oeste", "RN", "Apodi", "mixed"),
    UnitDef("Unidade Regional Central", "RN", "Angicos", "mixed"),
    UnitDef("Estação de Tratamento ETA Sul", "RN", "Natal", "operational"),
    UnitDef("Estação de Tratamento Mossoró", "RN", "Mossoró", "operational"),
    UnitDef("Laboratório CAERN", "RN", "Natal", "operational"),
]

# ---------------------------------------------------------------------------
# Employees per unit distribution
# ---------------------------------------------------------------------------

UNIT_EMPLOYEE_COUNT = {
    # MG
    "Sede Copasa BH": 500,
    "Estação de Tratamento Morro Vermelho": 350,
    "Unidade Regional Copasa Sul": 520,
    "Unidade Regional Copasa Triângulo": 520,
    "Unidade Regional Copasa Centro": 480,
    "Unidade Regional Copasa Leste": 400,
    "Unidade Regional Copasa Norte": 380,
    "Estação de Tratamento Rio Manso": 300,
    "Estação de Tratamento Serra Azul": 300,
    "Laboratório Central Copasa": 250,
    # RJ
    "Sede Águas do Rio Niterói": 500,
    "Estação de Tratamento Guandu": 400,
    "Unidade Rio Norte": 480,
    "Unidade Rio Sul": 450,
    "Unidade Rio Oeste": 420,
    "Unidade Rio Leste": 400,
    "Unidade Rio Centro": 350,
    "Estação de Tratamento Laranjal": 350,
    "Estação de Tratamento Alcântara": 350,
    "Laboratório Rio": 300,
    # RN
    "Sede CAERN Natal": 250,
    "Estação de Tratamento ETA Norte": 260,
    "Unidade Regional Mossoró": 250,
    "Unidade Regional Seridó": 200,
    "Unidade Regional Agreste": 220,
    "Unidade Regional Oeste": 200,
    "Unidade Regional Central": 180,
    "Estação de Tratamento ETA Sul": 220,
    "Estação de Tratamento Mossoró": 200,
    "Laboratório CAERN": 180,
}

# ---------------------------------------------------------------------------
# Schedule types available per state
# ---------------------------------------------------------------------------

SCHEDULES_BY_STATE = {
    "MG": ["5x2", "6x1", "12x36"],
    "RJ": ["5x2", "6x1", "12x36"],
    "RN": ["5x2", "3x3"],
}

# ---------------------------------------------------------------------------
# Dependents config
# ---------------------------------------------------------------------------

DEPENDENT_PERCENTAGE = 0.45  # % of employees who have at least 1 dependent
MAX_DEPENDENTS_PER_EMPLOYEE = 5
DEPENDENT_AGES_RANGE = (0, 25)  # age range for dependents (children generally)

# ---------------------------------------------------------------------------
# Inconsistency injection rates (0.0 to 1.0)
# ---------------------------------------------------------------------------

INCONSISTENCY_RATES = {
    "he_progressive_wrong": 0.08,
    "he_sunday_wrong": 0.06,
    "night_shift_missing": 0.05,
    "hour_bank_exceeded": 0.05,
    "interval_violation": 0.06,
    "point_vs_payroll_divergence": 0.04,
    "payment_divergence": 0.04,
    "missing_time_record": 0.03,
    "post_termination_payment": 0.02,
    "periculosidade_missing": 0.04,
    "insalubridade_missing": 0.04,
    "dsr_wrong": 0.05,
    "holiday_without_extra": 0.04,
    "hour_bank_negative_exceeded": 0.03,
    "cpf_divergent": 0.02,
    "orphan_payment": 0.02,
    "no_union": 0.02,
    "incompatible_schedule": 0.03,
    "duplicate_payment": 0.02,
    "overtime_without_approval": 0.06,
    "promotion_without_adjustment": 0.03,
    "night_shift_outside_range": 0.03,
    "weekly_limit_exceeded": 0.04,
    "wrong_union_cct": 0.02,
    "absence_deducted_wrongly": 0.03,
    "overlapping_journey": 0.02,
    "cct_temporal_mismatch": 0.02,
    "expired_vacation": 0.05,
    "impending_vacation": 0.06,
}

# ---------------------------------------------------------------------------
# Output paths
# ---------------------------------------------------------------------------

BRONZE_PATH = "data/bronze"
