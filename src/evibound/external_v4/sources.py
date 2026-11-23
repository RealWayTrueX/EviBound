"""Deterministic signed observation sources used by experiments and tests."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from typing import Any

from .model import SignedObservation
from .signing import ObservationSigner


class ScriptedSource:
    """Return queued envelopes, then the most recent envelope for that fact."""

    def __init__(
        self,
        signer: ObservationSigner,
        values: Mapping[str, Any],
        *,
        observed_at: float,
        sequence: int = 1,
        epoch: int = 1,
        record_prefix: str = "source",
    ) -> None:
        self._signer = signer
        self._next: dict[str, SignedObservation] = {}
        self._queues: dict[str, list[SignedObservation]] = defaultdict(list)
        for fact, value in values.items():
            self._queues[fact].append(
                signer.signed(
                    record_id=f"{record_prefix}-{fact}-{sequence}",
                    fact=fact,
                    value=value,
                    observed_at=observed_at,
                    sequence=sequence,
                    epoch=epoch,
                )
            )

    @classmethod
    def from_observations(
        cls, observations: Iterable[SignedObservation]
    ) -> "ScriptedSource":
        source = cls.__new__(cls)
        source._signer = None  # type: ignore[assignment]
        source._next = {}
        source._queues = defaultdict(list)
        for observation in observations:
            source._queues[observation.fact].append(observation)
        return source

    def read(self, fact: str, now: float) -> SignedObservation:
        del now
        queue = self._queues.get(fact, [])
        if not queue:
            raise KeyError(f"source has no observation for {fact}")
        if fact in self._next:
            return self._next[fact]
        observation = queue.pop(0)
        self._next[fact] = observation
        return observation


def source_from_context(
    signer: ObservationSigner,
    *,
    facts: Iterable[str],
    values: Mapping[str, Any],
    observed_at: float,
    sequence: int,
    epoch: int,
    forge: bool = False,
) -> ScriptedSource:
    observations: list[SignedObservation] = []
    for fact in facts:
        signed = signer.signed(
            record_id=f"context-{fact}-{sequence}",
            fact=fact,
            value=values[fact],
            observed_at=observed_at,
            sequence=sequence,
            epoch=epoch,
        )
        if forge:
            signed = signer.forge(
                signed,
                record_id=f"forged-{fact}-{sequence}",
                signature="0" * 64,
            )
        observations.append(signed)
    return ScriptedSource.from_observations(observations)
