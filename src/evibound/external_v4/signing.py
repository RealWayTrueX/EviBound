"""Deterministic device-signature emulation for the v4 proxy."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
from typing import Any

from .model import SignedObservation


def _canonical(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")


@dataclass(frozen=True)
class ObservationSigner:
    key: bytes

    def __post_init__(self) -> None:
        if len(self.key) < 16:
            raise ValueError("signing key must contain at least 16 bytes")

    def sign(self, observation: SignedObservation) -> str:
        return hmac.new(
            self.key, _canonical(observation.unsigned_payload()), hashlib.sha256
        ).hexdigest()

    def signed(
        self,
        *,
        record_id: str,
        fact: str,
        value: Any,
        observed_at: float,
        sequence: int,
        epoch: int = 1,
    ) -> SignedObservation:
        unsigned = SignedObservation(
            record_id=record_id,
            fact=fact,
            value=value,
            observed_at=observed_at,
            sequence=sequence,
            epoch=epoch,
            signature="",
        )
        return SignedObservation(**{**unsigned.as_dict(), "signature": self.sign(unsigned)})

    def verify(self, observation: SignedObservation) -> bool:
        expected = self.sign(observation)
        return hmac.compare_digest(expected, observation.signature)

    def forge(self, source: SignedObservation, **changes: Any) -> SignedObservation:
        """Return a well-formed but invalid envelope for channel-fault tests."""
        fields = source.as_dict()
        fields.update(changes)
        return SignedObservation(**fields)
