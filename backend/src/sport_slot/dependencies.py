from functools import lru_cache

import redis.asyncio as redis_asyncio
from google.cloud import firestore

from sport_slot.config import get_settings
from sport_slot.notifications.email.provider import EmailProvider
from sport_slot.notifications.email.resend_provider import ResendEmailProvider
from sport_slot.services.lock import LockService


@lru_cache
def get_firestore_client() -> firestore.Client:
    return firestore.Client(project=get_settings().gcp_project)


@lru_cache
def get_redis_client():
    settings = get_settings()
    return redis_asyncio.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        password=settings.redis_auth or None,
        socket_connect_timeout=2,
        socket_timeout=2,
    )


def get_lock_service() -> LockService:
    return LockService(get_redis_client())


@lru_cache
def get_email_provider() -> EmailProvider:
    settings = get_settings()
    return ResendEmailProvider(api_key=settings.resend_api_key, from_addr=settings.email_from_addr)
