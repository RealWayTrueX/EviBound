"""Append-only authentic observation store with replay rejection."""

from __future__ import annotations

from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Mapping

from .model import SignedObservation
from .signing import ObservationSigner


@dataclass(frozen=True)
class IngestResult:
    accepted: bool
    reason: str
    record: SignedObservation | None = None


class RecordStore:
    def __init__(self, signer: ObservationSigner, *, epoch: int = 1) -> None:
        self._signer = signer
        self._epoch = epoch
        self._records: dict[str, SignedObservation] = {}
        self._latest_by_fact: dict[str, str] = {}
        self._max_sequence: dict[str, int] = {}

    @property
    def records(self) -> Mapping[str, SignedObservation]:
        return MappingProxyType(dict(self._records))

    def ingest(self, observation: SignedObservation, *, now: float) -> IngestResult:
        if not self._signer.verify(observation):
            return IngestResult(False, "invalid_signature")
        if observation.epoch != self._epoch:
            return IngestResult(False, "wrong_epoch")
        if observation.observed_at - now > 1e-9:
            return IngestResult(False, "future_dated")
        previous = self._max_sequence.get(observation.fact, -1)
        if observation.sequence <= previous:
            return IngestResult(False, "stale_sequence")
        self._records[observation.record_id] = observation
        self._latest_by_fact[observation.fact] = observation.record_id
        self._max_sequence[observation.fact] = observation.sequence
        return IngestResult(True, "accepted", observation)

    def get(self, record_id: str) -> SignedObservation | None:
        return self._records.get(record_id)

    def latest(self, fact: str) -> SignedObservation | None:
        record_id = self._latest_by_fact.get(fact)
        return None if record_id is None else self._records[record_id]

    def latest_observed_at(self, fact: str) -> float:
        record = self.latest(fact)
        return -math.inf if record is None else record.observed_at
