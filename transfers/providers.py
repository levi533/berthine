from dataclasses import dataclass

from django.conf import settings
from django.utils.module_loading import import_string


@dataclass
class TransferProviderError(Exception):
    message: str
    outcome_unknown: bool = False


def get_transfer_provider():
    provider_path = settings.TRANSFER_PROVIDER_CLASS
    if not provider_path:
        return None

    provider_class = import_string(provider_path)
    provider = provider_class()
    if not callable(getattr(provider, "send_transfer", None)):
        raise TypeError(
            "The configured transfer provider must implement send_transfer(transfer, idempotency_key)."
        )
    return provider
