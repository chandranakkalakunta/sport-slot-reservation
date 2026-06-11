from functools import lru_cache

from google.cloud import firestore

from sport_slot.config import get_settings


@lru_cache
def get_firestore_client() -> firestore.Client:
    return firestore.Client(project=get_settings().gcp_project)
