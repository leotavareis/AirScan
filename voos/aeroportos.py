import json
from pathlib import Path

# Sugestões do campo de aeroporto. Qualquer código IATA de 3 letras é aceito;
# a lista só ajuda a achar o código digitando o nome da cidade.
#
# data/aeroportos.json vem do OurAirports (domínio público): aeroportos com código
# IATA e voos comerciais regulares. Para atualizar, gere de novo a partir de
# https://davidmegginson.github.io/ourairports-data/airports.csv

# Nomes em português, para achar digitando "Lisboa", "Londres" etc.
NOMES_PT = dict([
    # Brasil
    ("GRU", "São Paulo – Guarulhos"),
    ("CGH", "São Paulo – Congonhas"),
    ("VCP", "Campinas – Viracopos"),
    ("GIG", "Rio de Janeiro – Galeão"),
    ("SDU", "Rio de Janeiro – Santos Dumont"),
    ("BSB", "Brasília"),
    ("CNF", "Belo Horizonte – Confins"),
    ("PLU", "Belo Horizonte – Pampulha"),
    ("SSA", "Salvador"),
    ("REC", "Recife"),
    ("FOR", "Fortaleza"),
    ("NAT", "Natal"),
    ("JPA", "João Pessoa"),
    ("MCZ", "Maceió"),
    ("AJU", "Aracaju"),
    ("SLZ", "São Luís"),
    ("THE", "Teresina"),
    ("BPS", "Porto Seguro"),
    ("IOS", "Ilhéus"),
    ("FEN", "Fernando de Noronha"),
    ("JJD", "Jericoacoara"),
    ("POA", "Porto Alegre"),
    ("CWB", "Curitiba"),
    ("IGU", "Foz do Iguaçu"),
    ("LDB", "Londrina"),
    ("MGF", "Maringá"),
    ("FLN", "Florianópolis"),
    ("NVT", "Navegantes"),
    ("JOI", "Joinville"),
    ("XAP", "Chapecó"),
    ("CXJ", "Caxias do Sul"),
    ("BEL", "Belém"),
    ("MAO", "Manaus"),
    ("STM", "Santarém"),
    ("MCP", "Macapá"),
    ("BVB", "Boa Vista"),
    ("PVH", "Porto Velho"),
    ("RBR", "Rio Branco"),
    ("PMW", "Palmas"),
    ("GYN", "Goiânia"),
    ("CGB", "Cuiabá"),
    ("CGR", "Campo Grande"),
    ("BYO", "Bonito"),
    ("VIX", "Vitória"),
    ("UDI", "Uberlândia"),
    ("RAO", "Ribeirão Preto"),
    ("SJP", "São José do Rio Preto"),
    ("IMP", "Imperatriz"),
    ("JDO", "Juazeiro do Norte"),
    ("PNZ", "Petrolina"),
    # América do Sul
    ("EZE", "Buenos Aires – Ezeiza"),
    ("AEP", "Buenos Aires – Aeroparque"),
    ("BRC", "Bariloche"),
    ("MDZ", "Mendoza"),
    ("SCL", "Santiago"),
    ("MVD", "Montevidéu"),
    ("PDP", "Punta del Este"),
    ("ASU", "Assunção"),
    ("LIM", "Lima"),
    ("CUZ", "Cusco"),
    ("BOG", "Bogotá"),
    ("CTG", "Cartagena"),
    ("UIO", "Quito"),
    # América do Norte e Caribe
    ("MIA", "Miami"),
    ("FLL", "Fort Lauderdale"),
    ("MCO", "Orlando"),
    ("JFK", "Nova York – JFK"),
    ("EWR", "Nova York – Newark"),
    ("BOS", "Boston"),
    ("ATL", "Atlanta"),
    ("IAH", "Houston"),
    ("LAX", "Los Angeles"),
    ("LAS", "Las Vegas"),
    ("SFO", "São Francisco"),
    ("YYZ", "Toronto"),
    ("MEX", "Cidade do México"),
    ("CUN", "Cancún"),
    ("PUJ", "Punta Cana"),
    ("PTY", "Cidade do Panamá"),
    ("HAV", "Havana"),
    # Europa
    ("LIS", "Lisboa"),
    ("OPO", "Porto"),
    ("FAO", "Faro"),
    ("MAD", "Madri"),
    ("BCN", "Barcelona"),
    ("CDG", "Paris – Charles de Gaulle"),
    ("ORY", "Paris – Orly"),
    ("LHR", "Londres – Heathrow"),
    ("LGW", "Londres – Gatwick"),
    ("FCO", "Roma – Fiumicino"),
    ("MXP", "Milão – Malpensa"),
    ("VCE", "Veneza"),
    ("FRA", "Frankfurt"),
    ("MUC", "Munique"),
    ("BER", "Berlim"),
    ("AMS", "Amsterdã"),
    ("BRU", "Bruxelas"),
    ("ZRH", "Zurique"),
    ("VIE", "Viena"),
    ("PRG", "Praga"),
    ("DUB", "Dublin"),
    ("ATH", "Atenas"),
    ("IST", "Istambul"),
    # Outros
    ("DXB", "Dubai"),
    ("DOH", "Doha"),
    ("JNB", "Joanesburgo"),
    ("CPT", "Cidade do Cabo"),
    ("TLV", "Tel Aviv"),
    ("NRT", "Tóquio – Narita"),
    ("HND", "Tóquio – Haneda"),
    ("SYD", "Sydney"),
])


def _carregar():
    arquivo = Path(__file__).parent / "data" / "aeroportos.json"
    with arquivo.open(encoding="utf-8") as f:
        lista = json.load(f)
    resultado = []
    for codigo, rotulo in lista:
        nome_pt = NOMES_PT.get(codigo)
        resultado.append((codigo, f"{nome_pt} · {rotulo}" if nome_pt else rotulo))
    return resultado


AEROPORTOS = _carregar()
