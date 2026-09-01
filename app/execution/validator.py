import logging
from typing import Optional, List, Any
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.users.models import User
from app.execution.contracts import ExecutionRequest
from app.execution.models import StrategySignal, StrategyUserExecutionTrace
from app.strategies.models import Strategy, StrategyVersion, StrategyExecution
from app.execution.enums import ExecutionMode, LegRole

logger = logging.getLogger(__name__)

class ExecutionValidationResult(BaseModel):
    """Result of an ExecutionRequest validation and risk approval boundary check."""
    is_valid: bool
    failure_code: Optional[str] = None
    reason: str
    signal: Optional[Any] = None
    trace: Optional[Any] = None

    model_config = {
        "arbitrary_types_allowed": True
    }


class ExecutionValidator:
    """
    Authoritative Money-Safety Boundary for trade execution.
    Ensures that NO ExecutionRequest can reach the broker layer unless it originated
    from a valid backend StrategySignal and has an exact APPROVED risk decision.
    """

    @classmethod
    async def validate_execution_request(
        cls,
        db: AsyncSession,
        request: ExecutionRequest
    ) -> ExecutionValidationResult:
        correlation_id = request.correlation_id or "UNKNOWN"
        log_meta = {
            "event": "execution_validation_started",
            "strategy_id": request.strategy_id,
            "strategy_version_id": request.strategy_version_id,
            "signal_id": request.signal_id,
            "user_id": request.user_id,
            "correlation_id": correlation_id
        }
        logger.info(
            "execution_validation_started: strategy_id=%s version_id=%s signal_id=%s user_id=%s",
            request.strategy_id, request.strategy_version_id, request.signal_id, request.user_id,
            extra=log_meta
        )

        # 1. Validate ExecutionRequest Identity & Structure
        if (
            not request.user_id or request.user_id <= 0 or
            not request.strategy_id or request.strategy_id <= 0 or
            not request.strategy_version_id or request.strategy_version_id <= 0 or
            not request.signal_id or request.signal_id <= 0 or
            not request.correlation_id
        ):
            return cls._build_failed("INVALID_EXECUTION_REQUEST", "ExecutionRequest contains missing or invalid identity fields.", log_meta)

        if not request.legs or len(request.legs) == 0:
            return cls._build_failed("INVALID_EXECUTION_REQUEST", "ExecutionRequest contains no trade legs.", log_meta)

        for leg in request.legs:
            if leg.lots <= 0:
                return cls._build_failed("INVALID_EXECUTION_REQUEST", f"Leg {leg.leg_id} has non-positive lots: {leg.lots}.", log_meta)

        # 2. Verify Signal Exists
        stmt_sig = select(StrategySignal).where(StrategySignal.id == request.signal_id)
        res_sig = await db.execute(stmt_sig)
        signal = res_sig.scalar_one_or_none()

        if not signal:
            return cls._build_failed("SIGNAL_NOT_FOUND", f"Signal not found with ID: {request.signal_id}", log_meta)

        # 3. Verify Signal Strategy Ownership
        if signal.strategy_id != request.strategy_id:
            return cls._build_failed(
                "SIGNAL_STRATEGY_MISMATCH",
                f"Signal strategy_id {signal.strategy_id} does not match request strategy_id {request.strategy_id}.",
                log_meta
            )

        # 4. Verify Signal Version Ownership
        if signal.strategy_version_id != request.strategy_version_id:
            return cls._build_failed(
                "SIGNAL_VERSION_MISMATCH",
                f"Signal version {signal.strategy_version_id} does not match request version {request.strategy_version_id}.",
                log_meta
            )

        # 5. Verify Signal Status
        allowed_signal_statuses = ["CREATED", "TRIGGERED", "PROCESSING"]
        if signal.status not in allowed_signal_statuses:
            return cls._build_failed(
                "INVALID_SIGNAL_STATUS",
                f"Signal status '{signal.status}' is not eligible for execution (expected one of {allowed_signal_statuses}).",
                log_meta
            )

        # 6. Verify User Exists and is Eligible
        stmt_user = select(User).where(User.id == request.user_id)
        res_user = await db.execute(stmt_user)
        user = res_user.scalar_one_or_none()

        if not user:
            return cls._build_failed("USER_NOT_FOUND", f"User not found with ID: {request.user_id}", log_meta)

        if not user.is_active:
            return cls._build_failed("USER_NOT_ELIGIBLE", f"User ID {request.user_id} is inactive.", log_meta)

        # 7. Exact Persisted Risk Approval Verification
        stmt_trace = select(StrategyUserExecutionTrace).where(
            StrategyUserExecutionTrace.signal_id == request.signal_id,
            StrategyUserExecutionTrace.user_id == request.user_id
        )
        res_trace = await db.execute(stmt_trace)
        trace = res_trace.scalar_one_or_none()

        if not trace:
            return cls._build_failed("RISK_APPROVAL_MISSING", f"No risk evaluation trace found for signal {request.signal_id} and user {request.user_id}.", log_meta)

        if trace.strategy_id != request.strategy_id or trace.strategy_version_id != request.strategy_version_id:
            return cls._build_failed(
                "RISK_APPROVAL_MISMATCH",
                f"Risk approval belongs to strategy {trace.strategy_id} v{trace.strategy_version_id}, not request {request.strategy_id} v{request.strategy_version_id}.",
                log_meta
            )

        if trace.status in ["NOT_EXECUTED", "REJECTED", "FAILED", "BLOCKED"]:
            return cls._build_failed(
                "RISK_APPROVAL_REJECTED",
                f"Risk decision was rejected: {trace.failure_reason or trace.failure_code or trace.status}",
                log_meta
            )

        if trace.status == "EXECUTED":
            return cls._build_failed(
                "EXECUTION_DUPLICATE",
                f"Execution trace for signal {request.signal_id} and user {request.user_id} has already been EXECUTED.",
                log_meta
            )

        allowed_approved_statuses = ["PENDING", "PROCESSING", "RISK_APPROVED"]
        if trace.status not in allowed_approved_statuses:
            return cls._build_failed(
                "RISK_APPROVAL_MISSING",
                f"Risk trace status is '{trace.status}', which is not approved for execution.",
                log_meta
            )

        logger.info(
            "risk_approval_verified: user_id=%s signal_id=%s trace_id=%s status=%s",
            request.user_id, request.signal_id, trace.id, trace.status,
            extra={**log_meta, "event": "risk_approval_verified", "trace_id": trace.id}
        )

        # 8. Approved Quantity / Lots Verification
        for leg in request.legs:
            if leg.lots > request.approved_lots:
                return cls._build_failed(
                    "APPROVED_QUANTITY_EXCEEDED",
                    f"Requested lots ({leg.lots}) for leg {leg.leg_id} exceeds risk-approved multiplier ({request.approved_lots}).",
                    log_meta
                )

        # 9. Multi-Leg Package Consistency (Strategy 3)
        if len(request.legs) > 1:
            has_primary = any(l.role in [LegRole.PRIMARY, LegRole.ENTRY] for l in request.legs)
            has_hedge = any(l.role in [LegRole.HEDGE, LegRole.PROTECTION] for l in request.legs)
            ce_shorts = [l for l in request.legs if l.role == LegRole.PRIMARY and l.side == "SELL" and l.option_type == "CE"]
            ce_hedges = [l for l in request.legs if l.role == LegRole.HEDGE and l.side == "BUY" and l.option_type == "CE"]
            pe_shorts = [l for l in request.legs if l.role == LegRole.PRIMARY and l.side == "SELL" and l.option_type == "PE"]
            pe_hedges = [l for l in request.legs if l.role == LegRole.HEDGE and l.side == "BUY" and l.option_type == "PE"]

            if ce_shorts and not ce_hedges:
                return cls._build_failed(
                    "INVALID_EXECUTION_PACKAGE",
                    "Multi-leg CE option selling requires a mandatory CE hedge protection leg.",
                    log_meta
                )
            if pe_shorts and not pe_hedges:
                return cls._build_failed(
                    "INVALID_EXECUTION_PACKAGE",
                    "Multi-leg PE option selling requires a mandatory PE hedge protection leg.",
                    log_meta
                )
            if not has_hedge or not has_primary:
                return cls._build_failed(
                    "INVALID_EXECUTION_PACKAGE",
                    "Multi-leg option package must contain both a PRIMARY short leg and a HEDGE protection leg.",
                    log_meta
                )

        # 10. Execution Idempotency Verification
        stmt_exec = select(StrategyExecution).where(
            StrategyExecution.strategy_id == request.strategy_id,
            StrategyExecution.user_id == request.user_id,
            StrategyExecution.execution_trace_id == trace.id,
            StrategyExecution.status.in_(["RUNNING", "SUCCESS", "COMPLETED", "EXECUTED"])
        )
        res_exec = await db.execute(stmt_exec)
        if res_exec.scalar_one_or_none():
            logger.warning(
                "execution_duplicate_detected: user_id=%s signal_id=%s trace_id=%s",
                request.user_id, request.signal_id, trace.id,
                extra={**log_meta, "event": "execution_duplicate_detected", "trace_id": trace.id}
            )
            return cls._build_failed(
                "EXECUTION_DUPLICATE",
                f"An active or completed execution already exists for signal {request.signal_id} and user {request.user_id}.",
                log_meta
            )

        # 11. Execution Mode Verification (Trusted Backend)
        if request.execution_mode == ExecutionMode.LIVE:
            is_prod = getattr(settings, "ENVIRONMENT", "development") == "production"
            live_enabled = getattr(settings, "ENABLE_LIVE_TRADING", False)
            if not is_prod and not live_enabled:
                return cls._build_failed(
                    "INVALID_EXECUTION_MODE",
                    "LIVE execution mode is not permitted in non-production environment without explicit enable flag.",
                    log_meta
                )

        # 12. Validation Passed
        logger.info(
            "execution_validation_passed: user_id=%s signal_id=%s strategy_id=%s",
            request.user_id, request.signal_id, request.strategy_id,
            extra={**log_meta, "event": "execution_validation_passed"}
        )

        return ExecutionValidationResult(
            is_valid=True,
            reason="ExecutionRequest successfully validated against signal, risk approval, and idempotency boundaries.",
            signal=signal,
            trace=trace
        )

    @classmethod
    def _build_failed(cls, failure_code: str, reason: str, log_meta: dict) -> ExecutionValidationResult:
        logger.warning(
            "execution_validation_failed: failure_code=%s reason=%s",
            failure_code, reason,
            extra={**log_meta, "event": "execution_validation_failed", "failure_code": failure_code, "reason": reason}
        )
        return ExecutionValidationResult(
            is_valid=False,
            failure_code=failure_code,
            reason=reason
        )

execution_validator = ExecutionValidator()
