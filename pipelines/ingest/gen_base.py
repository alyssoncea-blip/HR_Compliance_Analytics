import random
import hashlib
from datetime import date, timedelta
from typing import List, Dict, Tuple
from dataclasses import dataclass

from config import (
    SEED, CCT_RULES, POSITIONS, UNITS, UNIT_EMPLOYEE_COUNT,
    SCHEDULES_BY_STATE, EMPLOYEES_PER_STATE, PERIOD_START, PERIOD_END,
    HIRE_DATE_START, HIRE_DATE_END,
)

random.seed(SEED)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FIRST_NAMES_M = [
    "João", "Carlos", "Antonio", "Francisco", "José", "Pedro", "Lucas", "Marcos",
    "Paulo", "Rafael", "Fernando", "Roberto", "Thiago", "Eduardo", "Bruno",
    "Felipe", "André", "Marcelo", "Diego", "Leonardo", "Gabriel", "Ricardo",
    "Alexandre", "Gustavo", "Henrique", "Rodrigo", "Fábio", "Luiz", "Márcio", "Sérgio",
    "Adriano", "Caio", "Daniel", "Enrique", "Geraldo", "Hugo", "Ivan", "Jorge",
    "Kleber", "Leandro", "Maurício", "Nelson", "Otávio", "Rogério", "Silvio",
    "Túlio", "Vagner", "Wagner", "Xavier", "Yuri", "Afonso", "Benedito", "César",
    "Davi", "Elias", "Flávio", "Gilberto", "Heitor", "Ismael", "Juliano", "Lorenzo",
    "Mateus", "Nicolas", "Osvaldo", "Raimundo", "Samuel", "Valdir", "William",
    "Alan", "Bernardo", "Cláudio", "Denis", "Edson", "Frederico", "Guilherme",
    "Hélio", "Igor", "Jonas", "Kevin", "Luan", "Miguel", "Natanael", "Oliver",
    "Patrick", "Renato", "Tomás", "Ulisses", "Vicente", "Wesley", "Arthur",
    "Benício", "Cauan", "Derek", "Erick", "Franklin", "Giovanni", "Hamilton",
    "Ítalo", "Joaquim", "Kaique", "Luigi", "Manoel", "Nathan", "Oscar", "Pablo",
    "Raul", "Stefan", "Tales", "Uriel", "Vitor", "Warley",
    "Abel", "Adalberto", "Ademar", "Adrián", "Aécio", "Aldo", "Alejandro", "Alessandro",
    "Alex", "Alfredo", "Almir", "Álvaro", "Amadeu", "Amaro", "Amílcar", "Ângelo",
    "Aníbal", "Antônio", "Aparecido", "Ari", "Armando", "Arnaldo", "Artur", "Aurélio",
    "Bartolomeu", "Bento", "Breno", "Caetano", "Calebe", "Cândido", "Cássio", "Cid",
    "Cícero", "Clemente", "Clóvis", "Conrado", "Cristiano", "Cristóvão", "Dario", "Davi",
    "Deivid", "Demétrio", "Dener", "Djalma", "Domingos", "Donizete", "Douglas", "Edmar",
    "Edmundo", "Edu", "Emanuel", "Emerson", "Emílio", "Enzo", "Ernesto", "Estêvão",
    "Eugênio", "Evan", "Evandro", "Everaldo", "Expedito", "Ezequiel", "Fabrício", "Feliciano",
    "Félix", "Fidélis", "Filipe", "Firmino", "Florisvaldo", "Francisco", "Frederico", "Gael",
    "Gasper", "Gerson", "Gian", "Giovane", "Glauber", "Godofredo", "Gonçalo", "Gregório",
    "Guido", "Gustavo", "Haroldo", "Hernani", "Horácio", "Humberto", "Igor", "Inácio",
    "Irineu", "Isaac", "Isaías", "Ivan", "Ivo", "Jacinto", "Jader", "Jaime",
    "Jair", "Januário", "Joaquim", "Jofre", "Jonas", "Jorge", "José", "Josué",
    "Juarez", "Júlio", "Júnior", "Júri", "Laércio", "Ladislau", "Lauro", "Lázaro",
    "Leandro", "Leônidas", "Levi", "Lindomar", "Lisandro", "Lívio", "Lourival", "Luan",
    "Luciano", "Luís", "Luiz", "Manoel", "Marcelo", "Marco", "Marcos", "Mário",
    "Mauro", "Maximiliano", "Miguel", "Milcíades", "Milton", "Moisés", "Murilo", "Natan",
    "Nélio", "Nestor", "Newton", "Nilson", "Nivaldo", "Noel", "Norberto", "Normando",
    "Odair", "Odilon", "Olavo", "Orlando", "Oscar", "Osni", "Oswaldo", "Otacílio",
    "Paolo", "Pascal", "Patric", "Paulo", "Pedro", "Plínio", "Rafael", "Raimundo",
    "Raul", "Reinaldo", "Renan", "Renato", "Ribamar", "Ricardo", "Roberto", "Robson",
    "Rodolfo", "Rodrigo", "Romário", "Rômulo", "Rubens", "Rui", "Salomão", "Salvador",
    "Sandro", "Sebastião", "Sérgio", "Severino", "Sidnei", "Silvano", "Silvério", "Simei",
    "Simão", "Sócrates", "Tadeu", "Teodoro", "Tertuliano", "Tiago", "Timóteo", "Tobias",
    "Tomás", "Toninho", "Ubirajara", "Ulysses", "Valdemar", "Valentim", "Valmir", "Vanderlei",
    "Ventura", "Vicente", "Victor", "Vinícius", "Virgílio", "Vital", "Vitor", "Vladimir",
    "Wagner", "Waldemar", "Walfredo", "Walter", "Washington", "Welington", "Wesley", "Wilian",
    "Wilson", "Xavier", "Xisto", "Yuri",
]
FIRST_NAMES_F = [
    "Maria", "Ana", "Carla", "Juliana", "Fernanda", "Patrícia", "Amanda",
    "Camila", "Letícia", "Vanessa", "Luciana", "Rebecca", "Rafaela", "Tatiane",
    "Bianca", "Priscila", "Daniela", "Renata", "Aline", "Cristiane", "Simone",
    "Adriana", "Beatriz", "Catarina", "Diana", "Eliane", "Fabiana", "Giovana",
    "Helena", "Ingrid", "Jéssica", "Karen", "Larissa", "Mariana", "Natália",
    "Olívia", "Paula", "Raquel", "Sandra", "Teresa", "Úrsula", "Viviane",
    "Wanessa", "Yasmin", "Alice", "Bruna", "Cecília", "Débora", "Elaine",
    "Flávia", "Gabriela", "Heloísa", "Isabela", "Jaqueline", "Kelly", "Liliane",
    "Mônica", "Nicole", "Orlanda", "Pâmela", "Rita", "Sueli", "Talita",
    "Valéria", "Wanda", "Ximena", "Yara", "Zilda", "Alessandra", "Barbara",
    "Claudia", "Daniele", "Erika", "Franciele", "Graciela", "Irene", "Janaina",
    "Karina", "Lorena", "Melissa", "Naiara", "Ondina", "Paloma", "Rosana",
    "Sabrina", "Tamires", "Vera", "Welida", "Andressa", "Bárbara", "Cláudia",
    "Dora", "Evelyn", "Fatima", "Gisele", "Iris", "Jucélia", "Kátia", "Lúcia",
    "Marta", "Nora", "Regina", "Sônia", "Tânia", "Vânia", "Aparecida", "Benilda",
    "Abigail", "Ada", "Adélia", "Adriana", "Ágata", "Agnes", "Aída", "Alba",
    "Albertina", "Alcina", "Alecsandra", "Aline", "Alzira", "Amália", "Ana", "Anabela",
    "Angelina", "Anita", "Antônia", "Aparecida", "Araci", "Ariana", "Arlinda", "Aurora",
    "Beatriz", "Benedita", "Berenice", "Bernadete", "Bianca", "Camila", "Carla", "Carmem",
    "Carolina", "Cassandra", "Catarina", "Cecília", "Célia", "Charlene", "Cíntia", "Clara",
    "Clarice", "Cláudia", "Cleide", "Cleusa", "Conceição", "Constância", "Cristina", "Cristiane",
    "Daiane", "Daisy", "Dalila", "Daniela", "Daniele", "Dayane", "Débora", "Deise",
    "Diana", "Dilma", "Dina", "Dinorá", "Dirce", "Dolores", "Dora", "Doroteia",
    "Edilene", "Edna", "Eduarda", "Elaine", "Eliana", "Eliane", "Elisa", "Elisabeth",
    "Elisângela", "Elza", "Ema", "Emília", "Erica", "Erika", "Esmeralda", "Estela",
    "Esther", "Eunice", "Eva", "Fabiana", "Fabrícia", "Fernanda", "Filipa", "Filomena",
    "Flávia", "Flor", "Flora", "Francisca", "Frederica", "Gabriela", "Giovana", "Gisela",
    "Gisele", "Graziela", "Guilhermina", "Helena", "Heloísa", "Henriqueta", "Hilda", "Hipólita",
    "Iara", "Idalina", "Inês", "Iolanda", "Irene", "Isabel", "Isabela", "Isadora",
    "Ivone", "Ivonete", "Jacira", "Jacqueline", "Jaqueline", "Jéssica", "Joana", "Jocélia",
    "Jordana", "Josefa", "Josiane", "Joyce", "Juciara", "Júlia", "Juliana", "Jussara",
    "Karine", "Kátia", "Keila", "Kelly", "Lais", "Lara", "Larissa", "Laura",
    "Lavínia", "Leila", "Leonora", "Letícia", "Lia", "Lígia", "Lilian", "Liliane",
    "Lívia", "Lorena", "Lourdes", "Luana", "Lúcia", "Luciana", "Luciene", "Luísa",
    "Luzia", "Madalena", "Mafalda", "Maira", "Malu", "Manuela", "Marcela", "Márcia",
    "Margarete", "Margarida", "Maria", "Mariana", "Marilene", "Marilza", "Marina", "Marisa",
    "Maristela", "Marta", "Matilde", "Maura", "Mayara", "Melina", "Melissa", "Mércia",
    "Michele", "Milena", "Mirela", "Mônica", "Naiara", "Nanci", "Natália", "Nayara",
    "Neide", "Nely", "Nicole", "Noemi", "Norma", "Núbia", "Olga", "Olívia",
    "Orlanda", "Otávia", "Pamela", "Pâmela", "Patricia", "Paula", "Poliana", "Priscila",
    "Quésia", "Raquel", "Rebeca", "Regina", "Renata", "Rita", "Roberta", "Rosa",
    "Rosana", "Rosângela", "Ruth", "Sandra", "Sara", "Sílvia", "Simone", "Sofia",
    "Solange", "Sônia", "Stela", "Stephanie", "Sueli", "Suellen", "Tainá", "Talita",
    "Tatiana", "Tatiane", "Tereza", "Teresa", "Tânia", "Valdirene", "Valéria", "Vanessa",
    "Vera", "Verônica", "Vicentina", "Violeta", "Virgínia", "Vivian", "Viviane", "Wanda",
    "Wilma", "Ximena", "Yara", "Yasmin", "Zilda", "Zuleica",
]
LAST_NAMES = [
    "Silva", "Santos", "Oliveira", "Souza", "Lima", "Pereira", "Costa",
    "Ferreira", "Almeida", "Rodrigues", "Nascimento", "Araújo", "Carvalho",
    "Gomes", "Martins", "Barbosa", "Ribeiro", "Dias", "Moreira", "Teixeira",
    "Monteiro", "Vieira", "Cavalcanti", "Mendes", "Cardoso", "Correia",
    "Sales", "Cunha", "Pires", "Campos",
    "Andrade", "Borges", "Castro", "Duarte", "Freitas", "Guimarães", "Machado",
    "Nunes", "Pinto", "Ramos", "Rezende", "Siqueira", "Tavares", "Vargas",
    "Xavier", "Braga", "Coelho", "Dantas", "Esteves", "Fonseca", "Guedes",
    "Lemos", "Marques", "Neves", "Peixoto", "Queiroz", "Rocha", "Saraiva",
    "Toledo", "Uchoa", "Viana", "Wanderley", "Aguiar", "Bittencourt", "Correa",
    "Farias", "Garcia", "Holanda", "Lacerda", "Moraes", "Medeiros", "Nogueira",
    "Oliveira", "Paiva", "Queiroga", "Reis", "Souto", "Trindade", "Vasconcelos",
]

CITIES = {
    "MG": ["Belo Horizonte", "Nova Lima", "Varginha", "Uberlândia", "Contagem", "Betim"],
    "RJ": ["Niterói", "Nova Iguaçu", "Duque de Caxias", "Rio de Janeiro", "São Gonçalo", "Petrópolis"],
    "RN": ["Natal", "Mossoró", "Caicó", "Parnamirim", "Assu", "Pau dos Ferros"],
}


def generate_cpf() -> str:
    n = [random.randint(0, 9) for _ in range(11)]
    return "".join(str(d) for d in n)


def _cpf_checksum(digits: List[int]) -> bool:
    d = digits[:9]
    s1 = sum((10 - i) * d[i] for i in range(9))
    dv1 = 0 if s1 % 11 < 2 else 11 - s1 % 11
    d.append(dv1)
    s2 = sum((11 - i) * d[i] for i in range(10))
    dv2 = 0 if s2 % 11 < 2 else 11 - s2 % 11
    return dv1 == digits[9] and dv2 == digits[10]


def generate_rg() -> str:
    return f"{random.randint(10,99)}.{random.randint(100,999)}.{random.randint(100,999)}-{random.randint(0,9)}"


def generate_bank_account() -> str:
    return f"{random.randint(1000,9999)}-{random.randint(0,9)}"


def random_date(start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))


def pick_weighted(options: List[Tuple[str, float]]) -> str:
    values, weights = zip(*options)
    return random.choices(values, weights=weights, k=1)[0]


# ---------------------------------------------------------------------------
# 1. Generate Positions (cargos)
# ---------------------------------------------------------------------------

def generate_positions() -> List[dict]:
    rows = []
    for i, pos in enumerate(POSITIONS, 1):
        rows.append({
            "position_id": i,
            "name": pos.name,
            "level": pos.level,
            "min_salary": pos.min_salary,
            "max_salary": pos.max_salary,
            "periculosidade_eligible": pos.periculosidade,
            "insalubridade_eligible": pos.insalubridade,
            "requires_approval_for_overtime": pos.requires_approval,
        })
    return rows


# ---------------------------------------------------------------------------
# 2. Generate Unions
# ---------------------------------------------------------------------------

def generate_unions() -> List[dict]:
    rows = []
    for i, cct in enumerate(CCT_RULES, 1):
        rows.append({
            "union_id": i,
            "state": cct.state,
            "name": cct.union_name,
            "company": cct.company,
            "standard_weekly_hours": cct.standard_weekly_hours,
            "cct_year_start": cct.year_start,
            "cct_year_end": cct.year_end,
            "he_weekday_percent": cct.he_weekday_percent,
            "he_sunday_percent": cct.he_sunday_percent,
            "he_holiday_percent": cct.he_holiday_percent,
            "he_progressive": cct.he_progressive,
            "he_first_hour_percent": cct.he_first_hour_percent,
            "he_additional_hours_percent": cct.he_additional_hours_percent,
            "night_shift_percent": cct.night_shift_percent,
            "night_shift_start": cct.night_shift_start,
            "night_shift_end": cct.night_shift_end,
            "periculosidade_percent": cct.periculosidade_percent,
            "insalubridade_percent": cct.insalubridade_percent,
            "max_hour_bank_hours": cct.max_hour_bank_hours,
            "min_rest_interval_hours": cct.min_rest_interval_hours,
            "salary_adjustment_percent": cct.salary_adjustment_percent,
            "base_salary_min": cct.base_salary_min,
            "meal_voucher_amount": cct.meal_voucher_amount,
            "food_basket_amount": cct.food_basket_amount,
            "plr_amount": cct.plr_amount,
        })
    return rows


# ---------------------------------------------------------------------------
# 3. Generate Units
# ---------------------------------------------------------------------------

def generate_units() -> List[dict]:
    rows = []
    for i, unit in enumerate(UNITS, 1):
        rows.append({
            "unit_id": i,
            "name": unit.name,
            "state": unit.state,
            "city": unit.city,
            "unit_type": unit.unit_type,
        })
    return rows


# ---------------------------------------------------------------------------
# 4. Generate Holidays (national + state)
# ---------------------------------------------------------------------------

NATIONAL_HOLIDAYS_FIXED = [
    (1, 1, "Confraternização Universal"),
    (4, 21, "Tiradentes"),
    (5, 1, "Dia do Trabalho"),
    (9, 7, "Independência"),
    (10, 12, "Nossa Sra. Aparecida"),
    (11, 2, "Finados"),
    (11, 15, "Proclamação da República"),
    (12, 25, "Natal"),
]

STATE_HOLIDAYS = {
    "MG": [(4, 21, "Tiradentes (em MG é feriado estadual)")],
    "RJ": [(4, 23, "Dia de São Jorge"), (11, 20, "Dia da Consciência Negra")],
    "RN": [(10, 3, "Mártires de Cunhaú e Uruaçu"), (11, 20, "Dia da Consciência Negra")],
}

# Carnival / Corpus Christi (moveis - simplified fixed)
MOVABLE_HOLIDAYS = [
    (2, 12, "Carnaval"),
    (2, 13, "Carnaval"),
    (2, 14, "Quarta-feira de Cinzas"),
    (5, 30, "Corpus Christi"),
]


def generate_holidays() -> List[dict]:
    rows = []
    hid = 1
    for year in range(PERIOD_START.year, PERIOD_END.year + 1):
        for m, d, name in NATIONAL_HOLIDAYS_FIXED:
            rows.append({"holiday_id": hid, "date": date(year, m, d), "state": "NATIONAL", "name": name})
            hid += 1
        for m, d, name in MOVABLE_HOLIDAYS:
            rows.append({"holiday_id": hid, "date": date(year, m, d), "state": "NATIONAL", "name": name})
            hid += 1
        for state, holidays in STATE_HOLIDAYS.items():
            for m, d, name in holidays:
                rows.append({"holiday_id": hid, "date": date(year, m, d), "state": state, "name": name})
                hid += 1
    return rows


# ---------------------------------------------------------------------------
# 5. Generate Employees
# ---------------------------------------------------------------------------

def _assign_unit(_state: str) -> dict:
    units_in_state = [u for u in UNITS if u.state == _state]
    if not units_in_state:
        raise ValueError(f"No units for state {_state}")
    weights = [UNIT_EMPLOYEE_COUNT[u.name] for u in units_in_state]
    return random.choices(units_in_state, weights=weights, k=1)[0]


def generate_employees() -> List[dict]:
    rows = []
    eid = 1

    # Build position distribution per level
    pos_by_level: Dict[str, List[int]] = {}
    for p in POSITIONS:
        pos_by_level.setdefault(p.level, []).append(p)

    # Build union mapping
    union_by_state = {c.state: i + 1 for i, c in enumerate(CCT_RULES)}

    # Track name usage to limit duplicates
    name_counter: Dict[str, int] = {}
    MAX_SAME_NAME = 20

    # Middle names pool for variety
    MIDDLE_NAMES_M = [
        "da Silva", "dos Santos", "de Oliveira", "de Souza", "de Lima", "de Pereira",
        "da Costa", "de Ferreira", "de Almeida", "de Rodrigues", "do Nascimento",
        "de Araújo", "de Carvalho", "de Gomes", "de Martins", "de Barbosa",
        "de Ribeiro", "de Dias", "de Moreira", "de Teixeira", "do Vale",
        "de Andrade", "de Borges", "de Castro", "de Duarte", "de Freitas",
        "de Guimarães", "de Machado", "de Nunes", "de Pinto", "de Ramos",
        "de Rezende", "de Siqueira", "de Tavares", "de Vargas", "de Xavier",
        "de Braga", "de Coelho", "de Dantas", "de Esteves", "da Fonseca",
        "de Guedes", "de Lemos", "de Marques", "das Neves", "de Peixoto",
        "de Queiroz", "da Rocha", "de Saraiva", "de Toledo", "de Uchoa",
        "de Viana", "de Wanderley", "de Aguiar", "de Bittencourt", "de Farias",
        "de Garcia", "de Holanda", "de Lacerda", "de Moraes", "de Medeiros",
        "de Nogueira", "de Paiva", "de Queiroga", "dos Reis", "de Souto",
        "da Trindade", "de Vasconcelos", "de Melo", "de Faria", "de Moraes",
        "da Conceição", "do Carmo", "da Paz", "da Luz", "do Amaral",
        "de Azevedo", "de Barros", "de Campos", "da Cunha", "de Furtado",
        "de Lira", "de Macedo", "de Moura", "de Neto", "de Novaes",
        "de Pacheco", "de Prado", "de Salles", "de Toledo", "de Vaz",
    ]
    MIDDLE_NAMES_F = [
        "da Silva", "dos Santos", "de Oliveira", "de Souza", "de Lima", "de Pereira",
        "da Costa", "de Ferreira", "de Almeida", "de Rodrigues", "do Nascimento",
        "de Araújo", "de Carvalho", "de Gomes", "de Martins", "de Barbosa",
        "de Ribeiro", "de Dias", "de Moreira", "de Teixeira", "do Vale",
        "de Andrade", "de Borges", "de Castro", "de Duarte", "de Freitas",
        "de Guimarães", "de Machado", "de Nunes", "de Pinto", "de Ramos",
        "de Rezende", "de Siqueira", "de Tavares", "de Vargas", "de Xavier",
        "de Braga", "de Coelho", "de Dantas", "de Esteves", "da Fonseca",
        "de Guedes", "de Lemos", "de Marques", "das Neves", "de Peixoto",
        "de Queiroz", "da Rocha", "de Saraiva", "de Toledo", "de Uchoa",
        "de Viana", "de Wanderley", "de Aguiar", "de Bittencourt", "de Farias",
        "de Garcia", "de Holanda", "de Lacerda", "de Moraes", "de Medeiros",
        "de Nogueira", "de Paiva", "de Queiroga", "dos Reis", "de Souto",
        "da Trindade", "de Vasconcelos", "de Melo", "de Faria", "de Moraes",
        "da Conceição", "do Carmo", "da Paz", "da Luz", "do Amaral",
        "de Azevedo", "de Barros", "de Campos", "da Cunha", "de Furtado",
        "de Lira", "de Macedo", "de Moura", "de Neto", "de Novaes",
        "de Pacheco", "de Prado", "de Salles", "de Toledo", "de Vaz",
    ]

    def _unique_name(gender: str) -> str:
        first_pool = FIRST_NAMES_M if gender == "M" else FIRST_NAMES_F
        middle_pool = MIDDLE_NAMES_M if gender == "M" else MIDDLE_NAMES_F
        use_middle = random.random() < 0.6  # 60% chance of having a middle name
        for _ in range(500):
            first = random.choice(first_pool)
            last = random.choice(LAST_NAMES)
            if use_middle:
                middle = random.choice(middle_pool)
                combo = f"{first} {middle} {last}"
            else:
                combo = f"{first} {last}"
            if name_counter.get(combo, 0) < MAX_SAME_NAME:
                name_counter[combo] = name_counter.get(combo, 0) + 1
                return combo
        # Fallback: add middle initial if all combos exhausted
        first = random.choice(first_pool)
        last = random.choice(LAST_NAMES)
        middle = random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        combo = f"{first} {middle}. {last}"
        name_counter[combo] = name_counter.get(combo, 0) + 1
        return combo

    for state, total in EMPLOYEES_PER_STATE.items():
        # Level distribution varies by state
        level_weights = {
            "MG": {"operational": 0.35, "technical": 0.20, "administrative": 0.25, "supervisor": 0.12, "management": 0.08},
            "RJ": {"operational": 0.30, "technical": 0.20, "administrative": 0.28, "supervisor": 0.14, "management": 0.08},
            "RN": {"operational": 0.40, "technical": 0.15, "administrative": 0.25, "supervisor": 0.12, "management": 0.08},
        }
        lw = level_weights[state]
        levels_list = list(lw.keys())
        levels_w = list(lw.values())

        schedules = SCHEDULES_BY_STATE[state]

        for _ in range(total):
            gender = random.choice(["M", "F"])
            name = _unique_name(gender)

            level_choice = random.choices(levels_list, weights=levels_w, k=1)[0]
            pos_list = pos_by_level[level_choice]
            position = random.choice(pos_list)
            salary = round(random.uniform(position.min_salary, position.max_salary), 2)

            # Hire date: wide range from 2005 to 2024
            hire_date = random_date(HIRE_DATE_START, HIRE_DATE_END)

            # 10% terminated
            terminated = random.random() < 0.10
            term_date = None
            term_type = None
            if terminated:
                term_date = random_date(date(2024, 7, 1), date(2026, 12, 31))
                term_type = random.choice(["resignation", "dismissal_without_cause", "retirement"])

            unit = _assign_unit(state)
            union_id = union_by_state[state]

            cpf = generate_cpf()
            weekly_hours = [c for c in CCT_RULES if c.state == state][0].standard_weekly_hours

            # For RN, schedule depends on level
            if state == "RN":
                if level_choice == "operational":
                    schedule = "3x3"
                else:
                    schedule = "5x2"
            else:
                schedule = random.choice(schedules)

            # Determine shift times based on schedule and level
            night_shift = False
            if state == "RN" and level_choice == "operational" and random.random() < 0.15:
                # Some RN operational are on night shift 3x3
                night_shift = True
            elif schedule == "12x36" and random.random() < 0.10:
                night_shift = True

            if night_shift:
                shift_entry_1 = "19:00"
                shift_exit_1 = "00:00"
                shift_entry_2 = None
                shift_exit_2 = None
                shift_type = "noturno"
            elif schedule == "3x3":
                shift_entry_1 = "07:00"
                shift_exit_1 = "12:00"
                shift_entry_2 = "13:00"
                shift_exit_2 = "19:00"
                shift_type = "diurno"
            elif schedule == "12x36":
                shift_entry_1 = "07:00"
                shift_exit_1 = "12:00"
                shift_entry_2 = "13:00"
                shift_exit_2 = "19:00"
                shift_type = "diurno"
            elif schedule == "6x1":
                shift_entry_1 = "08:00"
                shift_exit_1 = "12:00"
                shift_entry_2 = "13:00"
                shift_exit_2 = "17:00"
                shift_type = "diurno"
            else:  # 5x2
                if weekly_hours <= 30:
                    shift_entry_1 = "08:00"
                    shift_exit_1 = "12:00"
                    shift_entry_2 = "13:00"
                    shift_exit_2 = "15:00"
                else:
                    shift_entry_1 = "08:00"
                    shift_exit_1 = "12:00"
                    shift_entry_2 = "13:00"
                    shift_exit_2 = "17:00"
                shift_type = "diurno"

            rows.append({
                "employee_id": eid,
                "name": name,
                "cpf": cpf,
                "rg": generate_rg(),
                "gender": gender,
                "birth_date": random_date(date(1965, 1, 1), date(2002, 12, 31)),
                "education": pick_weighted([
                    ("fundamental", 0.15), ("medio", 0.40), ("superior", 0.35), ("pos", 0.10),
                ]),
                "position_id": position.position_id if hasattr(position, 'position_id') else POSITIONS.index(position) + 1,
                "unit_id": unit.unit_id if hasattr(unit, 'unit_id') else UNITS.index(unit) + 1,
                "union_id": union_id,
                "hire_date": hire_date,
                "termination_date": term_date,
                "termination_type": term_type,
                "work_schedule": schedule,
                "weekly_hours": weekly_hours,
                "shift_type": shift_type,
                "shift_entry_1": shift_entry_1,
                "shift_exit_1": shift_exit_1,
                "shift_entry_2": shift_entry_2,
                "shift_exit_2": shift_exit_2,
                "base_salary": salary,
                "bank_code": pick_weighted([("001", 0.40), ("237", 0.30), ("341", 0.15), ("033", 0.10), ("104", 0.05)]),
                "bank_agency": str(random.randint(1000, 9999)),
                "bank_account": generate_bank_account(),
                "dependents": random.choices([0, 1, 2, 3, 4], weights=[0.35, 0.30, 0.20, 0.10, 0.05], k=1)[0],
                "periculosidade_eligible": position.periculosidade,
                "insalubridade_eligible": position.insalubridade,
                "status": "terminated" if terminated else "active",
            })
            eid += 1

    return rows


# ---------------------------------------------------------------------------
# Helper: lookup maps for downstream scripts
# ---------------------------------------------------------------------------

def build_lookups(employees: List[dict], positions: List[dict], unions_: List[dict], units_: List[dict]):
    return {
        "employees": {e["employee_id"]: e for e in employees},
        "positions": {p["position_id"]: p for p in positions},
        "unions": {u["union_id"]: u for u in unions_},
        "units": {u["unit_id"]: u for u in units_},
        "cct_by_state": {c.state: c for c in CCT_RULES},
    }
