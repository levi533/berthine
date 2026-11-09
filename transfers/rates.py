from decimal import Decimal, ROUND_HALF_UP

CURRENCIES = {
    "EUR": "Euro",
    "XAF": "Franc CFA (BEAC)",
    "XOF": "Franc CFA (BCEAO)",
    "CHF": "Franc suisse",
    "CDF": "Franc congolais",
    "AOA": "Kwanza",
    "GHS": "Cedi",
    "NGN": "Naira",
    "CNY": "Yuan",
    "INR": "Roupie",
}

BASE_CORRIDORS = (
    ("EUR", "XAF", "655.957", "1.50"),
    ("EUR", "XOF", "655.957", "1.50"),
    ("EUR", "CDF", "2500.0", "1.50"),
    ("EUR", "AOA", "920.5", "1.50"),
    ("EUR", "GHS", "14.2", "1.50"),
    ("EUR", "NGN", "1650.0", "1.50"),
    ("EUR", "CHF", "0.96", "1.50"),
    ("EUR", "CNY", "7.65", "1.50"),
    ("EUR", "INR", "90.5", "1.50"),
    ("XAF", "EUR", "0.00153", "2000"),
    ("XOF", "EUR", "0.00153", "2000"),
    ("CDF", "EUR", "0.0004", "5000"),
    ("AOA", "EUR", "0.00109", "2000"),
    ("GHS", "EUR", "0.0704", "50"),
    ("NGN", "EUR", "0.000606", "2500"),
    ("CHF", "EUR", "1.042", "1.50"),
    ("CHF", "XAF", "682.8", "1.50"),
    ("CHF", "XOF", "682.8", "1.50"),
    ("CNY", "EUR", "0.1307", "1.50"),
    ("INR", "EUR", "0.01105", "1.50"),
)

WHOLE_UNIT_CURRENCIES = {"XAF", "XOF", "CDF", "NGN"}
CENT = Decimal("0.01")
RATE_PRECISION = Decimal("0.000001")
WHOLE_UNIT = Decimal("1")


def build_corridors():
    corridors = {
        (source, destination): {
            "rate": Decimal(rate),
            "fee": Decimal(fee),
        }
        for source, destination, rate, fee in BASE_CORRIDORS
    }

    for source in CURRENCIES:
        for destination in CURRENCIES:
            if source == destination or (source, destination) in corridors:
                continue
            to_euro = corridors.get((source, "EUR"))
            from_euro = corridors.get(("EUR", destination))
            if to_euro is None or from_euro is None:
                continue
            corridors[(source, destination)] = {
                "rate": (to_euro["rate"] * from_euro["rate"]).quantize(
                    RATE_PRECISION,
                    rounding=ROUND_HALF_UP,
                ),
                "fee": (
                    to_euro["fee"] + from_euro["fee"] / to_euro["rate"]
                ).quantize(CENT, rounding=ROUND_HALF_UP),
            }
    return corridors


CORRIDORS = build_corridors()


def quote(source, destination, amount):
    corridor = CORRIDORS.get((source, destination))
    if corridor is None:
        return None

    fee = corridor["fee"]
    net_amount = max(amount - fee, Decimal("0"))
    receive_amount = net_amount * corridor["rate"]
    precision = WHOLE_UNIT if destination in WHOLE_UNIT_CURRENCIES else CENT

    return {
        "source_currency": source,
        "destination_currency": destination,
        "source_amount": amount,
        "fee": fee,
        "exchange_rate": corridor["rate"],
        "receive_amount": receive_amount.quantize(
            precision,
            rounding=ROUND_HALF_UP,
        ),
        "indicative": True,
    }


def available_destinations():
    destinations = {currency: [] for currency in CURRENCIES}
    for source, destination in CORRIDORS:
        destinations[source].append(destination)
    return {
        source: sorted(codes)
        for source, codes in destinations.items()
        if codes
    }
