# BONGO

Site vitrine et API Django pour les comptes, les estimations de transfert et les avis.

## Démarrage local

Python 3.11 ou plus récent est recommandé.

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
set -a
. ./.env
set +a
```

Puis initialisez la base et démarrez le serveur :

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Les tests se lancent avec `python manage.py test`.

Le site est servi à `http://127.0.0.1:8000/` et l'administration à `http://127.0.0.1:8000/admin/`.

## API

- `GET /api/csrf/` — initialise le cookie CSRF.
- `POST /api/auth/register/`, `POST /api/auth/login/`, `POST /api/auth/logout/`, `GET /api/auth/me/`.
- `GET /api/transfers/currencies/`, `GET /api/transfers/quote/`.
- `POST /api/transfers/` et `GET /api/transfers/history/` — nécessitent une session.
- `GET /api/reviews/` — renvoie seulement les avis approuvés.
- `POST /api/reviews/` — soumet un avis lié à un transfert terminé; publication après modération.

Les requêtes JSON modifiant des données doivent inclure le jeton CSRF dans l'en-tête `X-CSRFToken`.

## Transferts réels

Les taux affichés sont des estimations configurées dans `transfers/rates.py`. Aucun prestataire de paiement n'est configuré par défaut : l'API renvoie alors `503` et ne crée ni ne prétend avoir envoyé un transfert. Avant toute utilisation réelle, configurez `TRANSFER_PROVIDER_CLASS` avec une implémentation Python de `send_transfer(transfer, idempotency_key)` qui appelle un prestataire agréé et traite les résultats de façon idempotente.

En production, définissez une clé `DJANGO_SECRET_KEY` forte, `DJANGO_DEBUG=False` et les hôtes dans `DJANGO_ALLOWED_HOSTS`. Utilisez HTTPS, configurez le prestataire et vérifiez les exigences réglementaires et de sécurité avant d'accepter des fonds.

## Déploiement sur Vercel

Vercel détecte Django à partir de `manage.py`, utilise `config/wsgi.py` et collecte automatiquement les fichiers de `STATIC_ROOT`. Aucun `vercel.json` personnalisé n'est nécessaire pour cette structure.

1. Importez `levi533/berthine` dans Vercel et gardez la racine du projet par défaut.
2. Créez ou connectez une base PostgreSQL persistante depuis un fournisseur compatible avec Vercel. Ajoutez son URL de connexion comme variable `DATABASE_URL` pour les environnements **Production** et **Preview**. SQLite reste réservé au développement local.
3. Dans les variables Vercel, configurez `DJANGO_SECRET_KEY` avec une valeur aléatoire forte, `DJANGO_DEBUG=False`, `DJANGO_ALLOWED_HOSTS` avec votre domaine de production (et les domaines `.vercel.app` utilisés pour les previews), et `DJANGO_CSRF_TRUSTED_ORIGINS` avec les origines HTTPS autorisées, par exemple `https://berthine.vercel.app`. N'ajoutez pas de secrets au dépôt.
4. Déployez depuis Vercel. Une fois le projet associé avec `vercel link` et les variables Production renseignées, appliquez les migrations à la base de production :

   ```bash
   vercel env run --environment production -- python manage.py migrate
   ```

5. Redéployez après toute modification des variables ou du code.

La clé secrète est obligatoire lorsque `DEBUG=False`; en production, une absence de configuration provoque une erreur explicite plutôt qu'un démarrage avec la clé de développement. Les transferts d'argent restent désactivés tant qu'aucun prestataire de paiement réel n'est intégré.
