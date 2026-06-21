"""Password-reset token repository — transactional single-use consume (ADR-0020 A2).

Lives in the repository layer (ADR-0008 Decision 3) because it uses a
Firestore transaction (@firestore.transactional) which is only allowed here.
"""

import datetime


class ResetTokenInvalid(Exception):
    """Raised when the token is missing, already used, or expired."""


def consume_reset_token(fs_client, token_hash: str) -> dict:
    """Atomically verify-and-consume a reset token. Returns {uid, tenant_id}.

    Raises ResetTokenInvalid if the token is missing, already used, or expired.
    The Firestore transaction is the authoritative single-use gate; the route
    should run a cheap non-authoritative pre-check before calling this.
    """
    from google.cloud import firestore

    ref = fs_client.collection("password_reset_tokens").document(token_hash)
    transaction = fs_client.transaction()

    @firestore.transactional
    def _run(txn):
        snap = ref.get(transaction=txn)
        if not snap.exists:
            raise ResetTokenInvalid()
        data = snap.to_dict() or {}
        if data.get("used"):
            raise ResetTokenInvalid()
        if data["expires_at"] <= datetime.datetime.now(datetime.UTC):
            raise ResetTokenInvalid()
        txn.update(ref, {"used": True})
        return {"uid": data["uid"], "tenant_id": data["tenant_id"]}

    return _run(transaction)
