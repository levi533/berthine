from decimal import Decimal, InvalidOperation
import logging
import re
import uuid

from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from accounts.services import normalize_phone, parse_json_body

from .models import Transfer
from .providers import TransferProviderError, get_transfer_provider
from .rates import CURRENCIES, available_destinations, quote

logger = logging.getLogger(__name__)
AMOUNT_PATTERN = re.compile(r"^\d{1,15}(?:\.\d{1,2})?$")


def require_authenticated_user(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Connectez-vous pour continuer."}, status=401)
    return None


def parse_amount(value):
    if not isinstance(value, (str, int, float)):
        return None
    amount_text = str(value).strip()
    if not AMOUNT_PATTERN.fullmatch(amount_text):
        return None
    try:
        amount = Decimal(amount_text)
    except InvalidOperation:
        return None
    return amount if amount.is_finite() and amount > 0 else None


def quote_payload(quote_data):
    return {
        key: str(value) if isinstance(value, Decimal) else value
        for key, value in quote_data.items()
    }


@require_GET
def currencies(request):
    return JsonResponse(
        {
            "currencies": [
                {"code": code, "name": name, "is_bceao": code == "XOF"}
                for code, name in CURRENCIES.items()
            ],
            "destinations": available_destinations(),
        }
    )


@require_GET
def create_quote(request):
    source = request.GET.get("source", "").upper()
    destination = request.GET.get("destination", "").upper()
    amount = parse_amount(request.GET.get("amount"))
    if source not in CURRENCIES or destination not in CURRENCIES or amount is None:
        return JsonResponse({"error": "Paramètres de calcul invalides."}, status=400)

    quote_data = quote(source, destination, amount)
    if quote_data is None:
        return JsonResponse({"error": "Cette destination n'est pas disponible."}, status=400)
    return JsonResponse(quote_payload(quote_data))


def transfer_payload(transfer):
    return {
        "id": str(transfer.pk),
        "source_currency": transfer.source_currency,
        "destination_currency": transfer.destination_currency,
        "source_amount": str(transfer.source_amount),
        "fee": str(transfer.fee),
        "exchange_rate": str(transfer.exchange_rate),
        "receive_amount": str(transfer.receive_amount),
        "recipient_name": transfer.recipient_name,
        "recipient_phone": transfer.recipient_phone,
        "status": transfer.status,
        "created_at": transfer.created_at.isoformat(),
    }


@require_GET
def transfer_history(request):
    unauthorized = require_authenticated_user(request)
    if unauthorized:
        return unauthorized
    transfers = Transfer.objects.filter(user=request.user).prefetch_related("review")
    return JsonResponse(
        {
            "transfers": [
                {
                    **transfer_payload(item),
                    "can_review": (
                        item.status == Transfer.Status.COMPLETED
                        and not hasattr(item, "review")
                    ),
                }
                for item in transfers
            ]
        }
    )


@require_POST
def create_transfer(request):
    unauthorized = require_authenticated_user(request)
    if unauthorized:
        return unauthorized

    data = parse_json_body(request)
    if data is None:
        return JsonResponse({"error": "Requête JSON invalide."}, status=400)

    source_value = data.get("source_currency")
    destination_value = data.get("destination_currency")
    source = source_value.upper() if isinstance(source_value, str) else ""
    destination = destination_value.upper() if isinstance(destination_value, str) else ""
    amount = parse_amount(data.get("amount"))
    try:
        idempotency_key = uuid.UUID(str(data.get("idempotency_key", "")))
    except (ValueError, AttributeError):
        idempotency_key = None
    name_value = data.get("recipient_name")
    recipient_name = name_value.strip() if isinstance(name_value, str) else ""
    recipient_phone = normalize_phone(data.get("recipient_phone"))
    if (
        source not in CURRENCIES
        or destination not in CURRENCIES
        or amount is None
        or idempotency_key is None
        or not recipient_name
        or len(recipient_name) > 120
        or not recipient_phone
    ):
        return JsonResponse({"error": "Informations de transfert invalides."}, status=400)

    quote_data = quote(source, destination, amount)
    if quote_data is None:
        return JsonResponse({"error": "Cette destination n'est pas disponible."}, status=400)

    try:
        provider = get_transfer_provider()
    except (ImportError, AttributeError, TypeError):
        logger.exception("The configured transfer provider could not be loaded.")
        return JsonResponse(
            {
                "error": (
                    "Le prestataire de transfert est mal configuré. "
                    "Aucun transfert n'a été lancé."
                )
            },
            status=503,
        )
    if provider is None:
        return JsonResponse(
            {
                "error": (
                    "L'envoi réel est indisponible : aucun prestataire de paiement "
                    "n'est configuré. Aucun argent n'a été envoyé."
                )
            },
            status=503,
        )

    transfer, created = Transfer.objects.get_or_create(
        idempotency_key=idempotency_key,
        defaults={
            "user": request.user,
            "source_currency": source,
            "destination_currency": destination,
            "source_amount": quote_data["source_amount"],
            "fee": quote_data["fee"],
            "exchange_rate": quote_data["exchange_rate"],
            "receive_amount": quote_data["receive_amount"],
            "recipient_name": recipient_name,
            "recipient_phone": recipient_phone,
        },
    )
    if not created:
        if transfer.user_id != request.user.pk:
            return JsonResponse({"error": "Cette clé de requête est déjà utilisée."}, status=409)
        if (
            transfer.source_currency != source
            or transfer.destination_currency != destination
            or transfer.source_amount != quote_data["source_amount"]
            or transfer.recipient_name != recipient_name
            or transfer.recipient_phone != recipient_phone
        ):
            return JsonResponse(
                {"error": "Cette clé de requête a déjà été utilisée avec d'autres informations."},
                status=409,
            )
        return JsonResponse({"transfer": transfer_payload(transfer)})

    try:
        result = provider.send_transfer(transfer, idempotency_key=str(idempotency_key))
    except TransferProviderError as error:
        if not error.outcome_unknown:
            transfer.status = Transfer.Status.FAILED
            transfer.save(update_fields=("status", "updated_at"))
        logger.error(
            "Transfer provider error for transfer %s (outcome_unknown=%s): %s",
            transfer.pk,
            error.outcome_unknown,
            error.message,
        )
        return JsonResponse(
            {"error": error.message, "transfer": transfer_payload(transfer)},
            status=502,
        )

    if not isinstance(result, dict) or result.get("status") not in Transfer.Status.values:
        logger.error("Transfer provider returned an invalid response for transfer %s.", transfer.pk)
        return JsonResponse(
            {
                "error": (
                    "Réponse invalide du prestataire. Vérifiez le statut avant toute nouvelle tentative."
                ),
                "transfer": transfer_payload(transfer),
            },
            status=502,
        )

    transfer.status = result["status"]
    transfer.provider_reference = str(result.get("provider_reference", ""))[:120]
    transfer.save(update_fields=("status", "provider_reference", "updated_at"))
    return JsonResponse({"transfer": transfer_payload(transfer)}, status=201)
