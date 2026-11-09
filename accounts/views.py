from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from .models import User
from .services import normalize_phone, parse_json_body


def user_payload(user):
    return {
        "id": user.pk,
        "phone": user.phone,
        "email": user.email,
        "first_name": user.first_name,
    }


@require_GET
@ensure_csrf_cookie
def csrf_token(request):
    return JsonResponse({"csrfToken": get_token(request)})


@require_POST
def register(request):
    data = parse_json_body(request)
    if data is None:
        return JsonResponse({"error": "Requête JSON invalide."}, status=400)

    phone = normalize_phone(data.get("phone"))
    password = data.get("password")
    email = data.get("email", "")
    if not phone:
        return JsonResponse({"error": "Numéro de téléphone invalide."}, status=400)
    if not isinstance(password, str):
        return JsonResponse({"error": "Mot de passe obligatoire."}, status=400)
    if not isinstance(email, str):
        return JsonResponse({"error": "Adresse e-mail invalide."}, status=400)
    email = email.strip()
    if len(email) > 254:
        return JsonResponse({"error": "Adresse e-mail invalide."}, status=400)
    if email:
        try:
            validate_email(email)
        except ValidationError:
            return JsonResponse({"error": "Adresse e-mail invalide."}, status=400)
    if User.objects.filter(phone=phone).exists():
        return JsonResponse({"error": "Un compte utilise déjà ce numéro."}, status=409)

    user = User(phone=phone, email=email)
    try:
        validate_password(password, user)
    except ValidationError as error:
        return JsonResponse({"error": " ".join(error.messages)}, status=400)

    user.set_password(password)
    user.save()
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    return JsonResponse({"user": user_payload(user)}, status=201)


@require_POST
def sign_in(request):
    data = parse_json_body(request)
    if data is None:
        return JsonResponse({"error": "Requête JSON invalide."}, status=400)

    phone = normalize_phone(data.get("phone"))
    password = data.get("password")
    if not phone or not isinstance(password, str):
        return JsonResponse({"error": "Téléphone ou mot de passe invalide."}, status=400)

    user = authenticate(request, phone=phone, password=password)
    if user is None:
        return JsonResponse({"error": "Identifiants incorrects."}, status=401)

    login(request, user)
    return JsonResponse({"user": user_payload(user)})


@require_POST
def sign_out(request):
    logout(request)
    return JsonResponse({"status": "signed_out"})


@require_GET
def current_user(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Connexion requise."}, status=401)
    return JsonResponse({"user": user_payload(request.user)})
