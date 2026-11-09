from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from accounts.services import parse_json_body
from transfers.models import Transfer

from .models import Review


def review_payload(review):
    return {
        "id": review.pk,
        "rating": review.rating,
        "text": review.text,
        "author": "Client BONGO",
        "created_at": review.created_at.isoformat(),
    }


@require_http_methods(["GET", "POST"])
def reviews(request):
    if request.method == "GET":
        published = Review.objects.filter(status=Review.Status.APPROVED).select_related(
            "transfer",
        )
        return JsonResponse({"reviews": [review_payload(item) for item in published]})

    if not request.user.is_authenticated:
        return JsonResponse({"error": "Connectez-vous pour déposer un avis."}, status=401)

    data = parse_json_body(request)
    if data is None:
        return JsonResponse({"error": "Requête JSON invalide."}, status=400)

    transfer_id = data.get("transfer_id")
    rating = data.get("rating")
    text = data.get("text")
    if not isinstance(transfer_id, str):
        return JsonResponse({"error": "Identifiant de transfert invalide."}, status=400)
    if not isinstance(rating, int) or isinstance(rating, bool) or not 1 <= rating <= 5:
        return JsonResponse({"error": "La note doit être comprise entre 1 et 5."}, status=400)
    if not isinstance(text, str) or not text.strip() or len(text.strip()) > 1000:
        return JsonResponse({"error": "L'avis doit contenir entre 1 et 1 000 caractères."}, status=400)

    transfer = Transfer.objects.filter(
        pk=transfer_id,
        user=request.user,
        status=Transfer.Status.COMPLETED,
    ).first()
    if transfer is None:
        return JsonResponse(
            {"error": "Un avis est possible uniquement après un transfert terminé."},
            status=400,
        )

    review, created = Review.objects.get_or_create(
        transfer=transfer,
        defaults={"rating": rating, "text": text.strip()},
    )
    if not created:
        return JsonResponse({"error": "Un avis existe déjà pour ce transfert."}, status=409)

    return JsonResponse(
        {
            "review": review_payload(review),
            "status": "pending_moderation",
        },
        status=201,
    )
