
import hashlib
import json
from datetime import datetime, timedelta
from uuid import UUID

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.idempotency import IdempotencyRecord


IDEMPOTENCY_VALID_HOURS = 24


def get_request_hash(request_body: dict) -> str:
    """
    Generate a consistent SHA-256 hash for the request body.
    The same JSON data produces the same hash even if key order differs.
    """
    encoded_body = jsonable_encoder(request_body)

    canonical_body = json.dumps(
        encoded_body,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    return hashlib.sha256(
        canonical_body.encode("utf-8")
    ).hexdigest()


def validate_idempotency_key(key: str) -> str:
    """
    Validate the Idempotency-Key as a UUID.
    Return its canonical string representation.
    """
    try:
        return str(UUID(key))
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(
            status_code=400,
            detail="Idempotency-Key must be a valid UUID.",
        )


def claim_idempotency(
    db: Session,
    user_id: int,
    endpoint: str,
    idempotency_key: str,
    request_body: dict,
):
    """
    Claim an idempotency key before processing a money request.

    Returns:
        ("NEW", record)     - New request; proceed with processing.
        ("REPLAY", record)  - Previously completed request; replay response.

    Raises:
        422 - Same key, different request body.
        409 - Same key is currently processing.
    """

    key = validate_idempotency_key(idempotency_key)
    request_hash = get_request_hash(request_body)
    now = datetime.utcnow()

    # Check for an existing record and lock it.
    existing = (
        db.query(IdempotencyRecord)
        .filter(
            IdempotencyRecord.user_id == user_id,
            IdempotencyRecord.endpoint == endpoint,
            IdempotencyRecord.idempotency_key == key,
        )
        .with_for_update()
        .first()
    )

    if existing:
        # Do not replace a request that may still be running.
        if existing.status == "PROCESSING":
            raise HTTPException(
                status_code=409,
                detail="A request with this Idempotency-Key is still processing.",
            )

        # An expired completed/failed key can be reused.
        if existing.expires_at <= now:
            db.delete(existing)
            db.commit()
        else:
            if existing.request_hash != request_hash:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        "This Idempotency-Key was already used "
                        "with a different request body."
                    ),
                )

            if existing.status == "COMPLETED":
                return "REPLAY", existing

            raise HTTPException(
                status_code=409,
                detail="This Idempotency-Key cannot currently be reused.",
            )

    # Create a new PROCESSING record.
    new_record = IdempotencyRecord(
        user_id=user_id,
        endpoint=endpoint,
        idempotency_key=key,
        request_hash=request_hash,
        status="PROCESSING",
        expires_at=now + timedelta(hours=IDEMPOTENCY_VALID_HOURS),
    )

    db.add(new_record)

    try:
        # This commit saves the claim separately from the money transaction.
        db.commit()
        db.refresh(new_record)
        return "NEW", new_record

    except IntegrityError:
        # Another request may have claimed this key at the same time.
        db.rollback()

        existing = (
            db.query(IdempotencyRecord)
            .filter(
                IdempotencyRecord.user_id == user_id,
                IdempotencyRecord.endpoint == endpoint,
                IdempotencyRecord.idempotency_key == key,
            )
            .with_for_update()
            .first()
        )

        if existing is None:
            raise HTTPException(
                status_code=409,
                detail="Unable to claim this Idempotency-Key. Please retry.",
            )

        if existing.request_hash != request_hash:
            raise HTTPException(
                status_code=422,
                detail="This Idempotency-Key was used with a different request body.",
            )

        if existing.status == "COMPLETED":
            return "REPLAY", existing

        raise HTTPException(
            status_code=409,
            detail="A request with this Idempotency-Key is still processing.",
        )


def save_idempotency_response(
    db: Session,
    record_id: int,
    response_status: int,
    response_body: dict,
):
    """
    Store the final response.

    IMPORTANT:
    Call this inside the same database transaction as the financial
    transaction, then commit once from the outer service.
    Do not commit inside this function.
    """

    record = (
        db.query(IdempotencyRecord)
        .filter(IdempotencyRecord.id == record_id)
        .with_for_update()
        .first()
    )

    if record is None:
        raise RuntimeError("Idempotency record was not found.")

    record.status = "COMPLETED"
    record.response_status = response_status
    record.response_body = jsonable_encoder(response_body)

    db.flush()

    return record
