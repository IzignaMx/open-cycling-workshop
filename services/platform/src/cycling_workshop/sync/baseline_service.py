"""Transaction-owned baseline progression; every successful response commits explicitly."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from cycling_workshop.api.errors import ApiError
from cycling_workshop.identity.context import build_context, lock_context
from cycling_workshop.identity.context_schemas import AccessContextResponse
from cycling_workshop.identity.security import SessionTokenService
from cycling_workshop.shared.ids import new_id
from cycling_workshop.sync.baseline_codec import (
    BaselineCodec,
    DecodedContinuation,
    reference_hash,
    token_hash,
)
from cycling_workshop.sync.baseline_models import BaselineFamily
from cycling_workshop.sync.baseline_queries import BaselineQueries, Candidate
from cycling_workshop.sync.baseline_schemas import (
    PAGE_LIMIT,
    RESPONSE_LIMIT,
    StartRequest,
    validate_record,
)
from cycling_workshop.sync.baseline_store import (
    aware,
    canonical,
    expire_and_admit,
    save_state,
    state,
)

READ_TYPES = {
    "customer": "customers.read",
    "bicycle": "bicycles.read",
    "service_order": "orders.read",
}


class BaselineService:
    def __init__(
        self,
        session: Session,
        tokens: SessionTokenService,
        codec: BaselineCodec,
        authorization: str | None,
    ):
        self.session, self.tokens, self.codec = session, tokens, codec
        self.deadline: datetime | None = None
        self.expiry_code = "baseline_expired"
        if session.get_bind().dialect.name == "postgresql":
            session.execute(text("SET LOCAL lock_timeout = '2s'"))
            session.execute(text("SET LOCAL statement_timeout = '5s'"))
        self.validated, self.principal = lock_context(session, tokens, authorization)

    def context(self, location: str) -> AccessContextResponse:
        context = build_context(self.session, self.tokens, self.validated, self.principal, location)
        if "sync.pull" not in context.capabilities:
            raise ApiError(403, "capability_denied", "capability denied")
        return context

    def queries(self, context: AccessContextResponse) -> BaselineQueries:
        return BaselineQueries(
            self.session,
            self.principal.organization_id,
            context.selected_location_id,
            [kind for kind, grant in READ_TYPES.items() if grant in context.capabilities],
        )

    def finish(self, body: str) -> str:
        if len(body.encode("utf-8")) > RESPONSE_LIMIT:
            raise ApiError(413, "projection_too_large", "projection exceeds response budget")
        # Includes cache replay; authentication may expire while waiting or serializing.
        self.session.flush()
        if self.validated.expires_at <= self.tokens.now():
            raise ApiError(401, "invalid_session", "invalid session")
        if self.deadline is not None and self.deadline <= self.tokens.now():
            raise ApiError(410, self.expiry_code, "pagination expired")
        self.session.commit()
        return body

    def start(self, request: StartRequest) -> str:
        context = self.context(request.selected_location_id)
        if request.authorization_epoch != context.authorization_epoch:
            raise ApiError(409, "context_changed", "authorization context changed")
        now = self.tokens.now()
        previous = self.session.scalar(
            select(BaselineFamily)
            .where(
                BaselineFamily.organization_id == self.principal.organization_id,
                BaselineFamily.user_id == self.principal.user_id,
                BaselineFamily.location_id == request.selected_location_id,
                BaselineFamily.epoch == request.authorization_epoch,
                BaselineFamily.request_id == request.request_id,
            )
            .with_for_update()
        )
        if previous is not None:
            if aware(previous.baseline_expires_at) <= now:
                raise ApiError(410, "baseline_expired", "baseline expired")
            self.deadline = aware(previous.baseline_expires_at)
            return self.finish(previous.start_json)
        expire_and_admit(
            self.session,
            self.principal.organization_id,
            self.principal.user_id,
            request.selected_location_id,
            now,
        )
        queries = self.queries(context)
        reference = self.codec.new_reference()
        baseline_id = new_id()
        baseline_expiry = min(now + timedelta(minutes=30), self.validated.expires_at)
        family_expiry = min(now + timedelta(hours=8), self.validated.expires_at)
        self.deadline = baseline_expiry
        body = canonical(
            {
                "protocol": 1,
                "baseline_id": baseline_id,
                "context": context.model_dump(mode="json"),
                "continuation": self.codec.encode(reference, 0, "scan"),
                "expires_at": baseline_expiry.isoformat().replace("+00:00", "Z"),
            }
        )
        if len(body.encode("utf-8")) > 16384:
            raise ApiError(413, "projection_too_large", "context exceeds response budget")
        family = BaselineFamily(
            reference_hash=reference_hash(reference),
            baseline_id=baseline_id,
            organization_id=self.principal.organization_id,
            user_id=self.principal.user_id,
            location_id=request.selected_location_id,
            epoch=context.authorization_epoch,
            request_id=request.request_id,
            created_at=now,
            baseline_expires_at=baseline_expiry,
            family_expires_at=family_expiry,
            retention_until=baseline_expiry,
            phase="scan",
            sequence=0,
            start_json=body,
            state_json="{}",
        )
        save_state(
            family,
            {
                "maxima": queries.maxima(),
                "positions": {},
                "type_index": 0,
                "cursor": queries.watermark(),
                "high": None,
                "baseline_run": True,
            },
        )
        self.session.add(family)
        return self.finish(body)

    def load(self, token: str) -> tuple[BaselineFamily, DecodedContinuation, AccessContextResponse]:
        decoded = self.codec.decode(token)
        family = self.session.scalar(
            select(BaselineFamily)
            .where(
                BaselineFamily.reference_hash == reference_hash(decoded.reference),
                BaselineFamily.organization_id == self.principal.organization_id,
                BaselineFamily.user_id == self.principal.user_id,
            )
            .with_for_update()
        )
        if family is None:
            raise ApiError(422, "cursor_invalid", "invalid continuation")
        context = self.context(family.location_id)
        if family.epoch != context.authorization_epoch:
            raise ApiError(409, "context_changed", "authorization context changed")
        self.deadline = aware(family.retention_until)
        self.expiry_code = (
            "baseline_expired"
            if family.phase in {"scan", "finalize", "baseline_delta"}
            else "checkpoint_expired"
        )
        if self.deadline <= self.tokens.now():
            code = (
                "baseline_expired"
                if family.phase in {"scan", "finalize", "baseline_delta"}
                else "checkpoint_expired"
            )
            raise ApiError(410, code, "pagination expired")
        return family, decoded, context

    def replay(self, family: BaselineFamily, token: str) -> str | None:
        if family.predecessor_hash == token_hash(token) and family.response_json is not None:
            return self.finish(family.response_json)
        return None

    @staticmethod
    def require(
        family: BaselineFamily, decoded: DecodedContinuation, purposes: set[str], phases: set[str]
    ) -> None:
        if (
            decoded.sequence != family.sequence
            or decoded.purpose not in purposes
            or family.phase not in phases
        ):
            raise ApiError(409, "continuation_stale", "continuation is not current for this phase")

    def advance(
        self,
        family: BaselineFamily,
        decoded: DecodedContinuation,
        token: str,
        purpose: str,
        body: dict[str, Any],
    ) -> str:
        family.sequence += 1
        body["continuation"] = self.codec.encode(decoded.reference, family.sequence, purpose)
        if body.get("phase") == "complete":
            body["completion"] = {
                "baseline_id": body["baseline_id"],
                "authorization_epoch": family.epoch,
                "checkpoint": body["continuation"],
            }
            if body["baseline_id"] is not None:
                family.activation_hash = token_hash(body["continuation"])
        encoded = canonical(body)
        if len(encoded.encode("utf-8")) > RESPONSE_LIMIT:
            raise ApiError(413, "projection_too_large", "projection exceeds response budget")
        family.predecessor_hash, family.response_json = token_hash(token), encoded
        return self.finish(encoded)

    def _record(self, queries: BaselineQueries, candidate: Candidate) -> dict[str, object]:
        # Stored JSON may use ASCII escapes (up to six bytes per Unicode byte).
        # Bound materialization separately from exact UTF-8 wire size; never load
        # arbitrary Text/JSON merely to discover that it is too large.
        allowance = (
            6 * RESPONSE_LIMIT if isinstance(candidate.position, int) else RESPONSE_LIMIT
        ) + 2048
        if candidate.estimated_bytes > allowance:
            raise ApiError(413, "projection_too_large", "projection exceeds response budget")
        try:
            projection = queries.load(candidate)
        except (ValueError, TypeError, KeyError) as exc:
            raise ApiError(409, "dataset_changed", "projection continuity changed") from exc
        return validate_record(projection, self.principal.organization_id, queries.location_id)

    def page(self, token: str) -> str:
        family, decoded, context = self.load(token)
        self.require_route(decoded, {"scan"})
        cached = self.replay(family, token)
        if cached is not None:
            return cached
        self.require(family, decoded, {"scan"}, {"scan"})
        data = state(family)
        queries = self.queries(context)
        types = list(data["maxima"])
        records: list[dict[str, object]] = []
        body: dict[str, Any] = {
            "protocol": 1,
            "baseline_id": family.baseline_id,
            "authorization_epoch": family.epoch,
            "page_id": new_id(),
            "predecessor": token,
            "records": records,
            "phase": "scan",
            "continuation": self.codec.encode(decoded.reference, family.sequence + 1, "scan"),
        }
        budget = RESPONSE_LIMIT - len(canonical(body).encode("utf-8")) + 1
        used = 0
        stop = False
        while data["type_index"] < len(types) and not stop:
            kind = types[data["type_index"]]
            maximum = data["maxima"][kind]
            if maximum is None:
                data["type_index"] += 1
                continue
            candidates = queries.scan_candidates(kind, data["positions"].get(kind), maximum)
            exhausted = len(candidates) < 101
            for candidate in candidates:
                if len(records) >= PAGE_LIMIT:
                    stop = True
                    break
                if candidate.estimated_bytes > budget - used and records:
                    stop = True
                    break
                record = self._record(queries, candidate)
                size = len(canonical(record).encode("utf-8")) + 1
                if used + size > budget:
                    if not records:
                        raise ApiError(
                            413, "projection_too_large", "projection exceeds response budget"
                        )
                    stop = True
                    break
                records.append(record)
                used += size
                data["positions"][kind] = candidate.position
            if exhausted and not stop:
                data["type_index"] += 1
        complete = data["type_index"] == len(types)
        if complete:
            body["phase"] = "scan_complete"
            body["continuation"] = self.codec.encode(
                decoded.reference, family.sequence + 1, "finalize"
            )
            if len(canonical(body).encode("utf-8")) > RESPONSE_LIMIT:
                # A near-limit record fits a scan page but not the longer final
                # envelope. Issue that page, then an empty final scan page.
                complete = False
                body["phase"] = "scan"
        family.phase = "finalize" if complete else "scan"
        save_state(family, data)
        return self.advance(family, decoded, token, "finalize" if complete else "scan", body)

    @staticmethod
    def require_route(decoded: DecodedContinuation, purposes: set[str]) -> None:
        if decoded.purpose not in purposes:
            raise ApiError(422, "cursor_invalid", "continuation is not valid for this endpoint")

    def finalize(self, token: str) -> str:
        family, decoded, context = self.load(token)
        self.require_route(decoded, {"finalize"})
        cached = self.replay(family, token)
        if cached is not None:
            return cached
        self.require(family, decoded, {"finalize"}, {"finalize"})
        data = state(family)
        data["high"] = self.queries(context).watermark()
        family.phase = "baseline_delta"
        save_state(family, data)
        return self.advance(
            family,
            decoded,
            token,
            "delta",
            {
                "protocol": 1,
                "baseline_id": family.baseline_id,
                "authorization_epoch": family.epoch,
                "predecessor": token,
            },
        )

    def delta(self, token: str) -> str:
        family, decoded, context = self.load(token)
        self.require_route(decoded, {"delta", "checkpoint"})
        cached = self.replay(family, token)
        if cached is not None:
            return cached
        self.require(
            family, decoded, {"delta", "checkpoint"}, {"baseline_delta", "delta", "complete"}
        )
        data = state(family)
        queries = self.queries(context)
        if decoded.purpose == "checkpoint":
            if family.phase != "complete":
                raise ApiError(409, "continuation_stale", "checkpoint is not current")
            data["high"] = queries.watermark()
            data["baseline_run"] = False
            family.activation_hash = None
            family.phase = "delta"
        elif family.phase == "complete":
            raise ApiError(409, "continuation_stale", "continuation is not current")
        if data["cursor"] > queries.watermark():
            raise ApiError(409, "dataset_changed", "dataset continuity changed")
        candidates = queries.delta_candidates(data["cursor"], data["high"])
        records: list[dict[str, object]] = []
        body: dict[str, Any] = {
            "protocol": 1,
            "baseline_id": family.baseline_id if data["baseline_run"] else None,
            "authorization_epoch": family.epoch,
            "page_id": new_id(),
            "predecessor": token,
            "records": records,
            "phase": "catching_up",
            "completion": None,
            "continuation": self.codec.encode(decoded.reference, family.sequence + 1, "delta"),
        }
        budget = RESPONSE_LIMIT - len(canonical(body).encode("utf-8")) + 1
        used = 0
        for candidate in candidates:
            if len(records) >= PAGE_LIMIT or (
                records and candidate.estimated_bytes > budget - used
            ):
                break
            record = self._record(queries, candidate)
            size = len(canonical(record).encode("utf-8")) + 1
            if used + size > budget:
                if not records:
                    raise ApiError(
                        413, "projection_too_large", "projection exceeds response budget"
                    )
                break
            records.append(record)
            used += size
            data["cursor"] = candidate.position
        complete = len(records) == len(candidates)
        if complete:
            checkpoint = self.codec.encode(decoded.reference, family.sequence + 1, "checkpoint")
            body.update(
                phase="complete",
                continuation=checkpoint,
                completion={
                    "baseline_id": body["baseline_id"],
                    "authorization_epoch": family.epoch,
                    "checkpoint": checkpoint,
                },
            )
            if len(canonical(body).encode("utf-8")) > RESPONSE_LIMIT:
                # Coverage is issued on a following empty page if its explicit
                # completion envelope cannot fit alongside this last record.
                complete = False
                body.update(phase="catching_up", completion=None)
        if complete:
            data["cursor"] = data["high"]
            family.phase = "complete"
            family.retention_until = family.family_expires_at
        save_state(family, data)
        return self.advance(family, decoded, token, "checkpoint" if complete else "delta", body)

    def activate(self, checkpoint: str) -> str:
        family, decoded, context = self.load(checkpoint)
        self.require_route(decoded, {"checkpoint"})
        self.require(family, decoded, {"checkpoint"}, {"complete"})
        if family.activation_hash != token_hash(checkpoint):
            raise ApiError(
                409, "continuation_stale", "baseline activation proof is no longer current"
            )
        return self.finish(
            canonical(
                {
                    "protocol": 1,
                    "baseline_id": family.baseline_id,
                    "authorization_epoch": family.epoch,
                    "checkpoint": checkpoint,
                    "context": context.model_dump(mode="json"),
                }
            )
        )
