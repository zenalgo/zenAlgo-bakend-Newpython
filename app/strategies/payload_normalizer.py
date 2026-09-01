from typing import Dict, Any, List, Optional
from decimal import Decimal
import uuid

from app.execution.enums import (
    ExecutionMode,
    OrderType,
    LegRole,
    OptionStrikePolicy,
    OptionExpiryPolicy
)
from app.execution.contracts import (
    LogicalLeg,
    ExecutionRequest
)

class FrontendPayloadNormalizer:
    """
    Normalizes Strategy Schema Version 2.0.0 JSON payloads from frontend into canonical
    domain representations (LogicalLegs, ExecutionRequests).
    Decouples raw JSON schema variations from execution engine logic.
    """

    @classmethod
    def normalize_strategy_legs(cls, payload: Dict[str, Any]) -> List[LogicalLeg]:
        """
        Parses option configuration or explicit legs from Strategy 1, 2, or 3 payloads.
        """
        options_config = payload.get("options", {})
        explicit_legs = options_config.get("legs", [])

        # Case A: Multi-leg explicitly defined (Strategy 3)
        if explicit_legs and isinstance(explicit_legs, list):
            normalized_legs: List[LogicalLeg] = []
            for idx, raw_leg in enumerate(explicit_legs):
                role_str = str(raw_leg.get("role", "PRIMARY")).upper()
                role = LegRole.HEDGE if "HEDGE" in role_str else (LegRole.PRIMARY if "SHORT" in role_str or "PRIMARY" in role_str else LegRole.PRIMARY)
                side = str(raw_leg.get("action", raw_leg.get("side", "BUY"))).upper()
                opt_type = str(raw_leg.get("optionType", "CE")).upper()

                # Parse strike policy and offset
                strike_selection_str = str(raw_leg.get("strikeSelection", "ATM")).upper()
                strike_policy = OptionStrikePolicy.ATM
                if "OTM" in strike_selection_str:
                    strike_policy = OptionStrikePolicy.OTM
                elif "ITM" in strike_selection_str:
                    strike_policy = OptionStrikePolicy.ITM
                elif "CUSTOM" in strike_selection_str:
                    strike_policy = OptionStrikePolicy.CUSTOM

                offset = Decimal(str(raw_leg.get("strikeOffset", raw_leg.get("offset", "0.0"))))
                expiry_str = str(raw_leg.get("expiry", "CURRENT_MONTHLY")).upper()
                expiry_policy = OptionExpiryPolicy.CURRENT_MONTHLY if "MONTH" in expiry_str else OptionExpiryPolicy.CURRENT_WEEKLY

                normalized_legs.append(LogicalLeg(
                    leg_id=raw_leg.get("legId", idx + 1),
                    sequence=raw_leg.get("sequence", idx + 1),
                    role=role,
                    side=side,
                    segment="OPT",
                    option_type=opt_type,
                    strike_policy=strike_policy,
                    strike_offset=offset,
                    expiry_policy=expiry_policy,
                    lots=int(raw_leg.get("lots", 1)),
                    order_type=OrderType.MARKET
                ))
            return normalized_legs

        # Case B: Single-leg configured via options block (Strategy 1 & 2)
        strike_sel = str(options_config.get("strikeSelection", "ATM")).upper()
        strike_policy = OptionStrikePolicy.ATM
        if "OTM" in strike_sel:
            strike_policy = OptionStrikePolicy.OTM
        elif "ITM" in strike_sel:
            strike_policy = OptionStrikePolicy.ITM

        expiry_type = str(payload.get("instrument", {}).get("expiryType", "CURRENT_WEEKLY")).upper()
        expiry_policy = OptionExpiryPolicy.CURRENT_WEEKLY if "WEEK" in expiry_type else OptionExpiryPolicy.CURRENT_MONTHLY

        # Default single-leg Option Buying setup
        return [
            LogicalLeg(
                leg_id=1,
                sequence=1,
                role=LegRole.PRIMARY,
                side="BUY",
                segment="OPT",
                option_type="CE", # Dynamically assigned based on signal direction
                strike_policy=strike_policy,
                strike_offset=Decimal("0.00"),
                expiry_policy=expiry_policy,
                lots=1,
                order_type=OrderType.MARKET
            )
        ]

    @classmethod
    def build_execution_request_from_signal(
        cls,
        payload: Dict[str, Any],
        user_id: int,
        strategy_id: int,
        strategy_version_id: int,
        signal_id: int,
        signal_type: str = "ENTRY",
        direction: str = "BUY",
        approved_lots: int = 1,
        required_capital: Decimal = Decimal("0.00"),
        execution_mode: ExecutionMode = ExecutionMode.PAPER
    ) -> ExecutionRequest:
        """
        Builds a canonical ExecutionRequest from a strategy payload and risk approval parameters.
        """
        underlying = payload.get("instrument", {}).get("underlying", "NIFTY")
        correlation_id = f"EXEC-SIG-{signal_id}-USR-{user_id}-{str(uuid.uuid4())[:8]}"
        logical_legs = cls.normalize_strategy_legs(payload)

        # Scale lots by risk-approved multiplier and adjust option_type by direction
        for leg in logical_legs:
            leg.lots = approved_lots
            if leg.option_type == "CE" and direction.upper() == "SELL":
                leg.option_type = "PE"

        exec_cfg = payload.get("execution", {})
        slippage = Decimal(str(exec_cfg.get("slippage", "0.5")))
        timeout = int(exec_cfg.get("orderTimeout", 30))

        return ExecutionRequest(
            user_id=user_id,
            strategy_id=strategy_id,
            strategy_version_id=strategy_version_id,
            signal_id=signal_id,
            signal_type=signal_type,
            direction=direction,
            execution_mode=execution_mode,
            underlying=underlying,
            correlation_id=correlation_id,
            legs=logical_legs,
            approved_lots=approved_lots,
            required_capital=required_capital,
            slippage_tolerance_pct=slippage,
            order_timeout_seconds=timeout
        )
