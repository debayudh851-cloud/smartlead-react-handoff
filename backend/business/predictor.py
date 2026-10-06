from functools import lru_cache
import math
from pathlib import Path
import joblib
import pandas as pd
from django.conf import settings
from django.db import transaction
from rest_framework.exceptions import APIException
from .models import MLPrediction, Notification


class PredictionUnavailable(APIException):
    status_code = 503
    default_detail = 'Prediction model unavailable. Train the trusted local model first.'


@lru_cache(maxsize=2)
def load_model(path, modified):
    # Only a trusted administrator-produced artifact path is accepted.
    return joblib.load(path)


def predict(lead):
    path = Path(settings.ML_MODEL_PATH)
    if not path.is_file():
        raise PredictionUnavailable()
    enquiry = lead.enquiry
    features = {
        'Lead Source': enquiry.traffic_source,
        'TotalVisits': enquiry.total_visits,
        'Total Time Spent on Website': enquiry.time_on_website,
        'Page Views Per Visit': enquiry.page_views_per_visit,
    }
    try:
        artifact = load_model(str(path), path.stat().st_mtime_ns)
        probability = float(artifact['pipeline'].predict_proba(pd.DataFrame([features]))[0, 1])
        if not math.isfinite(probability) or not 0 <= probability <= 1:
            raise ValueError('Invalid model probability')
        version = artifact['version']
    except Exception:
        raise PredictionUnavailable()
    band = 'HIGH' if probability >= settings.ML_HIGH_THRESHOLD else 'MEDIUM' if probability >= settings.ML_MEDIUM_THRESHOLD else 'LOW'
    with transaction.atomic():
        result = MLPrediction.objects.create(lead=lead, probability=probability, probability_band=band, model_version=version, features=features, is_demo=True)
        if band == 'HIGH':
            from django.contrib.auth import get_user_model
            for user in get_user_model().objects.filter(is_active=True, is_staff=True):
                Notification.objects.get_or_create(event_key=f'high:{lead.pk}:{version}:{user.pk}', defaults={'recipient': user, 'lead': lead, 'kind': 'HIGH_PROBABILITY', 'message': f'Lead #{lead.pk} has a high demo prediction.'})
    return result
