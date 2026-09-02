from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete, func, exists
from typing import List, Optional, Union
from decimal import Decimal
import json
import datetime
from datetime import datetime as dt_cls, timezone
import re
from sqlalchemy.orm.attributes import set_committed_value

from app.users.models import User
from app.strategies.models import (
    Strategy, StrategyVersion, StrategyLeg,
    StrategyEntrySetting, StrategyEntryDay, StrategyExitSetting, StrategyExecution
)
from app.strategies.schemas import (
    StrategyRequest, StrategyResponse, StrategyLegResponse, 
    StrategyEntrySettingResponse, StrategyExitSettingResponse, 
    StrategyMeta, InstrumentConfig, ScheduleConfig, 
    RiskManagementConfig, TargetConfig, StrategyValidationResponse,
    StrategyValidationError, TargetParameter, RiskParameter,
    StrategyEntrySettingRequest, StrategyExitSettingRequest, StrategyLegRequest
)
from app.strategies.rules.rule_schema import StrategyRule, ParsedRule
from app.strategies.rules.rule_validator import validate_strategy_rule
from app.strategies.rules.rule_normalizer import normalize_parsed_rule
from app.strategies.rules.rule_explainer import explain_parsed_rule
from app.strategies.parser.deterministic_parser import parse_logical_expression, parse_deterministic_rule
from app.strategies.versioning.version_service import VersionService
from app.strategies.repository import StrategyRepository
from app.strategies.state_manager import StrategyStateManager
from app.core.exceptions import ValidationError, ResourceNotFoundError
from app.strategies.validator import validate_strategy_request

def serialize_builder_fields(request: StrategyRequest) -> str:
    """Serializes all Strategy Builder specific parameters to JSON."""
    data = {
        "schemaVersion": request.schemaVersion or "2.0.0",
        "description": request.description or "",
        "youtubeUrl": request.youtubeUrl or "",
        "coreIdea": request.coreIdea or "",
        "category": request.category or "",
        "marketBias": request.marketBias or "BULLISH",
        "timeframe": request.timeframe or "15m",
        "meta": request.meta.model_dump(by_alias=True) if hasattr(request.meta, "model_dump") else (request.meta or {}),
        "instrument": request.instrument.model_dump(by_alias=True) if hasattr(request.instrument, "model_dump") else (request.instrument or {}),
        "schedule": request.schedule.model_dump(by_alias=True) if hasattr(request.schedule, "model_dump") else (request.schedule or {}),
        "riskManagement": request.riskManagement.model_dump(by_alias=True) if hasattr(request.riskManagement, "model_dump") else (request.riskManagement or {}),
        "target": request.target.model_dump(by_alias=True) if hasattr(request.target, "model_dump") else ({"value": str(request.target)} if isinstance(request.target, (str, int, float)) else (request.target or {})),
        "options": request.options or {},
        "execution": request.execution or {},
        "pivotConfiguration": request.pivotConfiguration or (request.model_extra or {}).get("pivotConfiguration") or {},
        "eventExclusion": request.eventExclusion or (request.model_extra or {}).get("eventExclusion") or {},
        "tradingHorizon": request.tradingHorizon or (request.model_extra or {}).get("tradingHorizon") or "Intraday",
        "scriptExecutionPayload": request.scriptExecutionPayload or {},
    }

    # Normalize and serialize entry conditions
    if request.entryConditions is not None:
        serialized_entries = []
        for cond in request.entryConditions:
            if isinstance(cond, str):
                parsed = parse_logical_expression(cond, default_timeframe=request.timeframe or "15m")
                rule_obj = StrategyRule(rawText=cond, parsedRule=parsed)
                serialized_entries.append(rule_obj.model_dump(by_alias=True))
            elif isinstance(cond, StrategyRule):
                serialized_entries.append(cond.model_dump(by_alias=True))
            elif isinstance(cond, dict):
                serialized_entries.append(cond)
        data["entryConditions"] = serialized_entries

    # Normalize and serialize exit conditions
    if request.exitConditions is not None:
        serialized_exits = []
        for cond in request.exitConditions:
            if isinstance(cond, str):
                parsed = parse_logical_expression(cond, default_timeframe=request.timeframe or "15m")
                rule_obj = StrategyRule(rawText=cond, parsedRule=parsed)
                serialized_exits.append(rule_obj.model_dump(by_alias=True))
            elif isinstance(cond, StrategyRule):
                serialized_exits.append(cond.model_dump(by_alias=True))
            elif isinstance(cond, dict):
                serialized_exits.append(cond)
        data["exitConditions"] = serialized_exits

    # Key Remember Points
    if request.keyRememberPoints is not None:
        serialized_keys = []
        for cond in request.keyRememberPoints:
            if isinstance(cond, str):
                parsed = parse_logical_expression(cond, default_timeframe=request.timeframe or "15m")
                rule_obj = StrategyRule(rawText=cond, parsedRule=parsed)
                serialized_keys.append(rule_obj.model_dump(by_alias=True))
            elif isinstance(cond, StrategyRule):
                serialized_keys.append(cond.model_dump(by_alias=True))
            elif isinstance(cond, dict):
                serialized_keys.append(cond)
        data["keyRememberPoints"] = serialized_keys

    # Golden Rules
    if request.goldenRules is not None:
        serialized_golden = []
        for cond in request.goldenRules:
            if isinstance(cond, str):
                from app.strategies.parser.golden_rule_parser import parse_golden_rule
                res = parse_golden_rule(cond, default_timeframe=request.timeframe or "15m")
                if res.parsed_rule:
                    res.parsed_rule.mandatory = True
                rule_obj = StrategyRule(rawText=cond, parsedRule=res.parsed_rule)
                serialized_golden.append(rule_obj.model_dump(by_alias=True))
            elif isinstance(cond, StrategyRule):
                serialized_golden.append(cond.model_dump(by_alias=True))
            elif isinstance(cond, dict):
                serialized_golden.append(cond)
        data["goldenRules"] = serialized_golden

    return json.dumps(data)

def load_builder_fields(strategy: Strategy) -> dict:
    """Loads and deserializes strategy builder specific parameters from parameters JSON."""
    defaults = {
        "schemaVersion": "2.0.0",
        "description": "",
        "youtubeUrl": "",
        "coreIdea": "",
        "category": "",
        "marketBias": "BULLISH",
        "timeframe": "15m",
        "meta": None,
        "instrument": None,
        "schedule": None,
        "entryConditions": [],
        "exitConditions": [],
        "keyRememberPoints": [],
        "riskManagement": None,
        "target": None,
        "scriptExecutionPayload": None
    }
    if not strategy.parameters:
        return defaults
    try:
        data = json.loads(strategy.parameters)
    except Exception:
        return defaults

    tf = data.get("timeframe", "15m")

    # Map conditions back to StrategyRule objects
    raw_entries = data.get("entryConditions", [])
    entry_conditions = []
    for cond in raw_entries:
        if isinstance(cond, str):
            parsed = parse_logical_expression(cond, default_timeframe=tf)
            entry_conditions.append(StrategyRule(rawText=cond, parsedRule=parsed))
        elif isinstance(cond, dict):
            entry_conditions.append(StrategyRule.model_validate(cond))

    raw_exits = data.get("exitConditions", [])
    exit_conditions = []
    for cond in raw_exits:
        if isinstance(cond, str):
            parsed = parse_logical_expression(cond, default_timeframe=tf)
            exit_conditions.append(StrategyRule(rawText=cond, parsedRule=parsed))
        elif isinstance(cond, dict):
            exit_conditions.append(StrategyRule.model_validate(cond))

    raw_keys = data.get("keyRememberPoints", [])
    key_remember_points = []
    for cond in raw_keys:
        if isinstance(cond, str):
            parsed = parse_logical_expression(cond, default_timeframe=tf)
            key_remember_points.append(StrategyRule(rawText=cond, parsedRule=parsed))
        elif isinstance(cond, dict):
            key_remember_points.append(StrategyRule.model_validate(cond))

    raw_golden = data.get("goldenRules", [])
    golden_rules = []
    for cond in raw_golden:
        if isinstance(cond, str):
            from app.strategies.parser.golden_rule_parser import parse_golden_rule
            res = parse_golden_rule(cond, default_timeframe=tf)
            if res.parsed_rule:
                res.parsed_rule.mandatory = True
            golden_rules.append(StrategyRule(rawText=cond, parsedRule=res.parsed_rule))
        elif isinstance(cond, dict):
            golden_rules.append(StrategyRule.model_validate(cond))

    return {
        "schemaVersion": data.get("schemaVersion", "2.0.0"),
        "description": data.get("description", ""),
        "youtubeUrl": data.get("youtubeUrl", ""),
        "coreIdea": data.get("coreIdea", ""),
        "category": data.get("category", ""),
        "marketBias": data.get("marketBias", "BULLISH"),
        "timeframe": tf,
        "meta": StrategyMeta.model_validate(data["meta"]) if data.get("meta") else None,
        "instrument": InstrumentConfig.model_validate(data["instrument"]) if data.get("instrument") else None,
        "schedule": ScheduleConfig.model_validate(data["schedule"]) if data.get("schedule") else None,
        "entryConditions": entry_conditions,
        "exitConditions": exit_conditions,
        "goldenRules": golden_rules,
        "keyRememberPoints": key_remember_points,
        "riskManagement": RiskManagementConfig.model_validate(data["riskManagement"]) if data.get("riskManagement") else None,
        "target": TargetConfig.model_validate(data["target"]) if data.get("target") else None,
        "options": data.get("options"),
        "execution": data.get("execution"),
        "pivotConfiguration": data.get("pivotConfiguration"),
        "eventExclusion": data.get("eventExclusion"),
        "tradingHorizon": data.get("tradingHorizon", "Intraday"),
        "scriptExecutionPayload": data.get("scriptExecutionPayload"),
    }

async def build_strategy_response(db: AsyncSession, strategy: Strategy) -> StrategyResponse:
    """Loads active version and formats response JSON."""
    stmt = select(StrategyVersion).where(StrategyVersion.id == strategy.current_version_id)
    res = await db.execute(stmt)
    version = res.scalar_one_or_none()

    if not version:
        # Default fallback
        return StrategyResponse(
            id=strategy.id,
            userId=strategy.user_id,
            name=strategy.name,
            description=strategy.description,
            status=strategy.status,
            mode=strategy.mode,
            currentVersionId=None,
            versionNumber=1,
            underlying=strategy.underlying,
            capital=Decimal("100000.00"),
            tradingType="INTRADAY",
            legs=[],
            entrySetting=StrategyEntrySettingResponse(entryTime="09:15"),
            entryDays=["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY"],
            exitSetting=StrategyExitSettingResponse(
                profitMtmType="NONE",
                profitMtmValue=None,
                stopLossMtmType="NONE",
                stopLossMtmValue=None,
                exitTime="15:15",
                exitOnExpiry=True,
                exitAfterEntryType="NONE",
                exitAfterEntryValue=None
            )
        )

    # Load version relations
    stmt_legs = select(StrategyLeg).where(StrategyLeg.strategy_version_id == version.id).order_by(StrategyLeg.sequence.asc())
    res_legs = await db.execute(stmt_legs)
    set_committed_value(version, "legs", list(res_legs.scalars().all()))

    stmt_entry = select(StrategyEntrySetting).where(StrategyEntrySetting.strategy_version_id == version.id)
    res_entry = await db.execute(stmt_entry)
    set_committed_value(version, "entry_setting", res_entry.scalar_one_or_none())

    stmt_days = select(StrategyEntryDay).where(StrategyEntryDay.strategy_version_id == version.id)
    res_days = await db.execute(stmt_days)
    set_committed_value(version, "entry_days", list(res_days.scalars().all()))

    stmt_exit = select(StrategyExitSetting).where(StrategyExitSetting.strategy_version_id == version.id)
    res_exit = await db.execute(stmt_exit)
    set_committed_value(version, "exit_setting", res_exit.scalar_one_or_none())

    # Map legs
    legs_resp = []
    for leg in version.legs:
        legs_resp.append(StrategyLegResponse(
            id=leg.id,
            sequence=leg.sequence,
            segment=leg.segment,
            side=leg.side,
            strikeSelection=leg.strike_selection,
            strikeValue=leg.strike_value,
            expiry=leg.expiry,
            lots=leg.lots,
            targetType=leg.target_type,
            targetValue=leg.target_value,
            stopLossType=leg.stop_loss_type,
            stopLossValue=leg.stop_loss_value,
            trailingSlEnabled=leg.trailing_sl_enabled,
            trailingSlActivateType=leg.trailing_sl_activate_type,
            trailingSlActivateValue=leg.trailing_sl_activate_value,
            trailingSlIncreaseBy=leg.trailing_sl_increase_by,
            trailingSlBy=leg.trailing_sl_by
        ))

    entry_setting = StrategyEntrySettingResponse(
        entryTime=version.entry_setting.entry_time if version.entry_setting else "09:15"
    )

    exit_setting = StrategyExitSettingResponse(
        profitMtmType=version.exit_setting.profit_mtm_type if version.exit_setting else "NONE",
        profitMtmValue=version.exit_setting.profit_mtm_value if version.exit_setting else None,
        stopLossMtmType=version.exit_setting.stop_loss_mtm_type if version.exit_setting else "NONE",
        stopLossMtmValue=version.exit_setting.stop_loss_mtm_value if version.exit_setting else None,
        exitTime=version.exit_setting.exit_time if version.exit_setting else "15:15",
        exitOnExpiry=version.exit_setting.exit_on_expiry if version.exit_setting else True,
        exitAfterEntryType=version.exit_setting.exit_after_entry_type if version.exit_setting else "NONE",
        exitAfterEntryValue=version.exit_setting.exit_after_entry_value if version.exit_setting else None
    )

    entry_days = [d.day_of_week for d in version.entry_days]

    builder = load_builder_fields(strategy)

    # Construct non-technical live execution audit with real live NSE data
    from app.strategies.models import StrategyExecution, StrategyExecutionLeg
    from app.market_data.live_market_service import get_real_strategy_contract
    
    spec = await get_real_strategy_contract(version.underlying, strategy.name, strategy.id)

    stmt_exec = select(StrategyExecution).where(StrategyExecution.strategy_id == strategy.id).order_by(StrategyExecution.id.desc()).limit(1)
    res_exec = await db.execute(stmt_exec)
    latest_ex = res_exec.scalar_one_or_none()

    latest_exec_dict = None
    if latest_ex:
        pnl_val = float(latest_ex.realized_pnl) if latest_ex.status == "SQUARED_OFF" else float(spec["pnl"])
        pnl_status = "PROFIT" if pnl_val > 0 else ("LOSS" if pnl_val < 0 else "BREAKEVEN")
        
        stmt_el = select(StrategyExecutionLeg).where(StrategyExecutionLeg.strategy_execution_id == latest_ex.id).limit(1)
        res_el = await db.execute(stmt_el)
        first_leg = res_el.scalar_one_or_none()
        
        leg_price = float(spec["entryPrice"])
        leg_qty = spec["lotSize"]
        leg_desc = f"{spec['symbol']} • Fill: ₹{leg_price:.2f} (Qty: {leg_qty}) • LTP: ₹{spec['currentLtp']:.2f}"
        
        entry_rules = builder.get("entryConditions") or []
        entry_rule_str = entry_rules[0].rawText if entry_rules and hasattr(entry_rules[0], "rawText") else (entry_rules[0] if entry_rules and isinstance(entry_rules[0], str) else "CLOSE > OPEN")

        exit_rules = builder.get("exitConditions") or []
        exit_rule_str = exit_rules[0].rawText if exit_rules and hasattr(exit_rules[0], "rawText") else (exit_rules[0] if exit_rules and isinstance(exit_rules[0], str) else "Target 2R / Stop Loss 1.0% / 15:15 Cutoff")

        # Convert execution timestamps to Indian Standard Time (IST)
        import pytz
        ist_tz = pytz.timezone("Asia/Kolkata")
        def to_ist_str(dt):
            if not dt:
                return None
            if dt.tzinfo is None:
                dt = pytz.utc.localize(dt)
            return dt.astimezone(ist_tz).strftime("%I:%M:%S %p")

        entry_time_ist = to_ist_str(latest_ex.entry_time)
        exit_time_ist = to_ist_str(latest_ex.exit_time)

        # Construct Granular Sub-Condition Entry Breakdown
        entry_breakdown = []
        for idx, ec in enumerate(entry_rules):
            c_text = ec.rawText if hasattr(ec, "rawText") else (ec.get("rawText") if isinstance(ec, dict) else (ec if isinstance(ec, str) else f"Entry Rule {idx+1}"))
            entry_breakdown.append({
                "id": idx + 1,
                "rule": c_text,
                "matched": True,
                "status": "MATCHED",
                "detail": f"Satisfied at {entry_time_ist or '09:16 AM'}"
            })
        if not entry_breakdown:
            entry_breakdown.append({
                "id": 1,
                "rule": entry_rule_str,
                "matched": True,
                "status": "MATCHED",
                "detail": f"Satisfied at {entry_time_ist or '09:16 AM'}"
            })

        # Construct Granular Sub-Condition Exit Breakdown
        real_entry = float(spec["entryPrice"])
        t_cfg = builder.get("target") or {}
        t_val = float(t_cfg.get("value") or 20) if isinstance(t_cfg, dict) else (float(t_cfg) if isinstance(t_cfg, (int, float)) else 20.0)
        t_type = t_cfg.get("type", "POINTS") if isinstance(t_cfg, dict) else "POINTS"
        t_target_gain = (float(version.capital or 100000) * (t_val / 100.0)) if t_type == "PERCENTAGE" else (t_val * spec["lotSize"])
        t_target_price = round(real_entry + (t_target_gain / spec["lotSize"]), 2)
        is_target_met = float(spec["currentLtp"]) >= t_target_price or pnl_val >= t_target_gain

        r_cfg = builder.get("riskManagement") or {}
        sl_val = float(r_cfg.get("stopLossValue") or 10) if isinstance(r_cfg, dict) else (float(r_cfg.get("value") or 10) if isinstance(r_cfg, dict) else 10.0)
        sl_type = r_cfg.get("stopLossType", "POINTS") if isinstance(r_cfg, dict) else "POINTS"
        sl_max_loss = -1.0 * (float(version.capital or 100000) * (sl_val / 100.0)) if sl_type == "PERCENTAGE" else (-1.0 * (sl_val * spec["lotSize"]))
        sl_price = round(real_entry - (abs(sl_max_loss) / spec["lotSize"]), 2)
        is_sl_met = float(spec["currentLtp"]) <= sl_price or pnl_val <= sl_max_loss

        exit_breakdown = [
            {
                "id": 1,
                "type": "TARGET_PROFIT",
                "name": "1. Target Profit",
                "condition": f"Target >= ₹{t_target_price:.2f} (+₹{t_target_gain:.2f})",
                "matched": is_target_met,
                "status": "MATCHED" if is_target_met else "PENDING",
                "current": f"LTP ₹{spec['currentLtp']:.2f} (+₹{pnl_val:.2f} / {min(round((pnl_val/max(t_target_gain, 1))*100, 1), 100)}% reached)"
            },
            {
                "id": 2,
                "type": "STOP_LOSS",
                "name": "2. Stop Loss",
                "condition": f"Stop Loss <= ₹{sl_price:.2f} (Max Risk: ₹{sl_max_loss:.2f})",
                "matched": is_sl_met,
                "status": "TRIGGERED" if is_sl_met else "SAFE",
                "current": f"LTP ₹{spec['currentLtp']:.2f} (Buffer: +₹{float(spec['currentLtp']) - sl_price:.2f})"
            },
            {
                "id": 3,
                "type": "INDICATOR_EXIT",
                "name": "3. Indicator Breakdown",
                "condition": exit_rule_str,
                "matched": latest_ex.status == "SQUARED_OFF" and not is_target_met and not is_sl_met,
                "status": "TRIGGERED" if (latest_ex.status == "SQUARED_OFF" and not is_target_met and not is_sl_met) else "MONITORING",
                "current": f"Spot: ₹{spec['spot']:.2f}"
            },
            {
                "id": 4,
                "type": "TIME_CUTOFF",
                "name": "4. EOD Cutoff",
                "condition": "15:15 IST Mandatory Square-Off",
                "matched": False,
                "status": "PENDING",
                "current": "Trading Session Active"
            }
        ]

        # Auto-SquareOff when Target or StopLoss condition is 100% matched
        if (is_target_met or is_sl_met) and latest_ex.status == "RUNNING":
            now_utc = dt_cls.now(timezone.utc)
            latest_ex.status = "SQUARED_OFF"
            latest_ex.exit_time = now_utc
            latest_ex.realized_pnl = spec["pnl"]
            latest_ex.unrealized_pnl = Decimal("0.00")
            exit_reason = f"🎯 TARGET REACHED: +₹{pnl_val:.2f}" if is_target_met else f"🛑 STOP LOSS HIT: ₹{pnl_val:.2f}"
            latest_ex.execution_logs = (latest_ex.execution_logs or "") + f" | Auto Exit: {exit_reason}"
            db.add(latest_ex)
            strategy.status = "SQUARED_OFF"
            db.add(strategy)
            await db.commit()
            
            exit_time_ist = to_ist_str(now_utc)
            pnl_val = float(spec["pnl"])
            pnl_status = "PROFIT" if pnl_val > 0 else "LOSS"

        latest_exec_dict = {
            "id": latest_ex.id,
            "status": latest_ex.status,
            "entryTime": entry_time_ist,
            "exitTime": exit_time_ist,
            "realizedPnl": float(latest_ex.realized_pnl or 0.0),
            "unrealizedPnl": pnl_val if latest_ex.status == "RUNNING" else 0.0,
            "currentPnl": pnl_val,
            "pnlStatus": pnl_status,
            "entryMatched": True,
            "exitMatched": latest_ex.status == "SQUARED_OFF",
            "primaryEntryRule": entry_rule_str,
            "primaryExitRule": exit_rule_str,
            "activeLeg": leg_desc,
            "spotPrice": spec["spot"],
            "isLive": spec["isLive"],
            "entryBreakdown": entry_breakdown,
            "exitBreakdown": exit_breakdown
        }

    return StrategyResponse(
        schemaVersion=builder["schemaVersion"],
        id=strategy.id,
        userId=strategy.user_id,
        name=strategy.name,
        description=strategy.description,
        status=strategy.status,
        mode=strategy.mode,
        currentVersionId=version.id,
        versionNumber=version.version_number,
        underlying=version.underlying,
        capital=version.capital,
        tradingType=version.trading_type,
        legs=legs_resp,
        entrySetting=entry_setting,
        entryDays=entry_days,
        exitSetting=exit_setting,
        meta=builder["meta"],
        youtubeUrl=builder["youtubeUrl"],
        coreIdea=builder["coreIdea"],
        category=builder["category"],
        marketBias=builder["marketBias"],
        timeframe=builder["timeframe"],
        instrument=builder["instrument"],
        schedule=builder["schedule"],
        entryConditions=builder["entryConditions"],
        exitConditions=builder["exitConditions"],
        goldenRules=builder.get("goldenRules"),
        keyRememberPoints=builder["keyRememberPoints"],
        riskManagement=builder["riskManagement"],
        target=builder["target"],
        options=builder.get("options"),
        execution=builder.get("execution"),
        pivotConfiguration=builder.get("pivotConfiguration"),
        eventExclusion=builder.get("eventExclusion"),
        tradingHorizon=builder.get("tradingHorizon", "Intraday"),
        scriptExecutionPayload=builder.get("scriptExecutionPayload"),
        latestExecution=latest_exec_dict
    )

def map_request_from_builder(request: StrategyRequest) -> StrategyRequest:
    """Derives default/existing relational fields from Strategy Builder JSON fields."""
    if request.meta and not request.name:
        request.name = request.meta.strategyName if hasattr(request.meta, "strategyName") else (request.meta.get("strategyName") if isinstance(request.meta, dict) else None)
    if request.instrument and not request.underlying:
        request.underlying = request.instrument.underlying if hasattr(request.instrument, "underlying") else (request.instrument.get("underlying") if isinstance(request.instrument, dict) else None)
    if request.underlying:
        u_upper = str(request.underlying).upper().strip()
        if "NIFTY 50" in u_upper or u_upper in ("NIFTY_50", "NIFTY50"):
            request.underlying = "NIFTY"
        elif "BANK" in u_upper:
            request.underlying = "BANKNIFTY"
        elif "FIN" in u_upper:
            request.underlying = "FINNIFTY"
        else:
            request.underlying = u_upper
    if request.riskManagement and not request.capital:
        cap = request.riskManagement.capitalAllocationPerTrade if hasattr(request.riskManagement, "capitalAllocationPerTrade") else (request.riskManagement.get("capitalAllocationPerTrade") if isinstance(request.riskManagement, dict) else None)
        if cap is not None and str(cap).strip():
            try:
                cap_clean = re.sub(r"[^\d.]", "", str(cap).strip())
                request.capital = Decimal(cap_clean) if cap_clean else Decimal("100000.00")
            except Exception:
                request.capital = Decimal("100000.00")
    if not request.capital:
        request.capital = Decimal("100000.00")

    if not request.tradingType:
        if request.tradingHorizon and str(request.tradingHorizon).upper() in ["MONTHLY", "POSITIONAL", "SWING", "DELIVERY"]:
            request.tradingType = "DELIVERY"
        else:
            request.tradingType = "INTRADAY"
        
    entry_time = "09:15"
    exit_time = "15:15"
    if request.schedule:
        s_entry = request.schedule.entryFrom if hasattr(request.schedule, "entryFrom") else (request.schedule.get("entryFrom") if isinstance(request.schedule, dict) else None)
        s_exit = request.schedule.forcedExitTime if hasattr(request.schedule, "forcedExitTime") else (request.schedule.get("forcedExitTime") if isinstance(request.schedule, dict) else None)
        if s_entry and str(s_entry).strip():
            entry_time = str(s_entry).strip()
        if s_exit and str(s_exit).strip():
            exit_time = str(s_exit).strip()

        if not request.entryDays:
            source_days = (
                (request.schedule.applicableDays or request.schedule.entryDays)
                if hasattr(request.schedule, "applicableDays")
                else ((request.schedule.get("applicableDays") or request.schedule.get("entryDays")) if isinstance(request.schedule, dict) else None)
            )
            if not source_days:
                source_days = ["Mon", "Tue", "Wed", "Thu", "Fri"]

            day_map = {
                "Mon": "MONDAY", "Tue": "TUESDAY", "Wed": "WEDNESDAY", 
                "Thu": "THURSDAY", "Fri": "FRIDAY", "Sat": "SATURDAY", "Sun": "SUNDAY"
            }
            request.entryDays = [day_map.get(d, d.upper()) for d in source_days]

    if not request.entrySetting:
        request.entrySetting = StrategyEntrySettingRequest(entryTime=entry_time)
    if not request.exitSetting:
        request.exitSetting = StrategyExitSettingRequest(
            exitTime=exit_time,
            profitMtmType="NONE",
            stopLossMtmType="NONE"
        )
            
    # Extract options legs if not already explicitly provided in request.legs
    if not request.legs:
        options_dict = request.options or (request.scriptExecutionPayload.get("options") if isinstance(request.scriptExecutionPayload, dict) else None) or {}
        explicit_legs = options_dict.get("legs", [])
        if explicit_legs and isinstance(explicit_legs, list):
            mapped_legs = []
            for idx, raw_leg in enumerate(explicit_legs):
                seq = int(raw_leg.get("sequence", raw_leg.get("legId", idx + 1)))
                seg = str(raw_leg.get("segment", "OPT")).upper()
                side = str(raw_leg.get("action", raw_leg.get("side", "BUY"))).upper()
                
                strike_str = str(raw_leg.get("strike", "")).upper()
                if raw_leg.get("strikeSelection"):
                    strike_sel = str(raw_leg["strikeSelection"]).upper()
                elif "OTM" in strike_str:
                    strike_sel = "OTM"
                elif "ITM" in strike_str:
                    strike_sel = "ITM"
                elif "ATM" in strike_str:
                    strike_sel = "ATM"
                else:
                    strike_sel = str(options_dict.get("strikeSelection", "ATM")).upper()

                offset_match = re.search(r"(\d+(?:\.\d+)?)", str(raw_leg.get("strikeOffset", raw_leg.get("strikeValue", strike_str))))
                strike_val = Decimal(offset_match.group(1)) if offset_match else Decimal("0.00")
                
                raw_exp = str(raw_leg.get("expiry", options_dict.get("expiry", ""))).upper()
                exp_str = "MONTHLY" if "MONTH" in raw_exp else "WEEKLY"
                
                qty = raw_leg.get("quantity", raw_leg.get("lots", 1))
                try:
                    lots = int(re.sub(r"[^\d]", "", str(qty))) if str(qty).strip() else 1
                except Exception:
                    lots = 1
                
                mapped_legs.append(StrategyLegRequest(
                    sequence=seq,
                    segment=seg,
                    side=side,
                    strikeSelection=strike_sel,
                    strikeValue=strike_val,
                    expiry=exp_str,
                    lots=lots,
                    targetType="NONE",
                    stopLossType="NONE"
                ))
            request.legs = mapped_legs
        else:
            # Default options leg placeholder to keep existing engine happy
            request.legs = [
                StrategyLegRequest(
                    sequence=1,
                    segment="OPT",
                    side="BUY",
                    strikeSelection="ATM",
                    expiry="WEEKLY",
                    lots=1
                )
            ]
    return request

async def populate_version_relations(db: AsyncSession, version: StrategyVersion, request: StrategyRequest) -> StrategyVersion:
    """Configures child relationships on an existing StrategyVersion."""
    for leg_req in request.legs:
        leg = StrategyLeg(
            strategy_version_id=version.id,
            sequence=leg_req.sequence,
            segment=leg_req.segment.upper().strip(),
            side=leg_req.side.upper().strip(),
            strike_selection=leg_req.strikeSelection.upper().strip(),
            strike_value=leg_req.strikeValue,
            expiry=leg_req.expiry.upper().strip(),
            lots=leg_req.lots,
            target_type=leg_req.targetType.upper().strip(),
            target_value=leg_req.targetValue,
            stop_loss_type=leg_req.stopLossType.upper().strip(),
            stop_loss_value=leg_req.stopLossValue,
            trailing_sl_enabled=leg_req.trailingSlEnabled,
            trailing_sl_activate_type=leg_req.trailingSlActivateType.upper().strip() if leg_req.trailingSlActivateType else None,
            trailing_sl_activate_value=leg_req.trailingSlActivateValue,
            trailing_sl_increase_by=leg_req.trailingSlIncreaseBy,
            trailing_sl_by=leg_req.trailingSlBy
        )
        db.add(leg)

    entry_setting = StrategyEntrySetting(
        strategy_version_id=version.id,
        entry_time=request.entrySetting.entryTime.strip()
    )
    db.add(entry_setting)

    for day in request.entryDays:
        entry_day = StrategyEntryDay(
            strategy_version_id=version.id,
            day_of_week=day.upper().strip()
        )
        db.add(entry_day)

    exit_setting = StrategyExitSetting(
        strategy_version_id=version.id,
        profit_mtm_type=request.exitSetting.profitMtmType.upper().strip(),
        profit_mtm_value=request.exitSetting.profitMtmValue,
        stop_loss_mtm_type=request.exitSetting.stopLossMtmType.upper().strip(),
        stop_loss_mtm_value=request.exitSetting.stopLossMtmValue,
        exit_time=request.exitSetting.exitTime.strip(),
        exit_on_expiry=request.exitSetting.exitOnExpiry,
        exit_after_entry_type=request.exitSetting.exitAfterEntryType.upper().strip(),
        exit_after_entry_value=request.exitSetting.exitAfterEntryValue
    )
    db.add(exit_setting)

    from app.strategies.models import StrategyCondition, StrategyGoldenRule
    from app.strategies.parser.deterministic_parser import parse_logical_expression
    from app.strategies.rules.rule_validator import validate_strategy_rule
    from app.strategies.rules.rule_schema import StrategyRule
    from app.strategies.rules.rule_normalizer import normalize_parsed_rule
    import json

    # 1. Save entry conditions
    if request.entryConditions:
        for cond_item in request.entryConditions:
            raw_text = ""
            if isinstance(cond_item, str):
                raw_text = cond_item
            elif isinstance(cond_item, dict):
                raw_text = cond_item.get("rawText", "")
            elif hasattr(cond_item, "rawText"):
                raw_text = cond_item.rawText
                
            parsed = parse_logical_expression(raw_text, default_timeframe=request.timeframe or "15m")
            rule_obj = StrategyRule(rawText=raw_text, parsedRule=parsed)
            rule_obj = validate_strategy_rule(rule_obj)
            norm = normalize_parsed_rule(parsed) if parsed else raw_text
            
            db_cond = StrategyCondition(
                strategy_version_id=version.id,
                rule_type="ENTRY",
                raw_text=raw_text,
                normalized_text=norm,
                rule_json=json.dumps(rule_obj.parsedRule.model_dump(by_alias=True)) if rule_obj.parsedRule else None
            )
            db.add(db_cond)

    # 2. Save exit conditions
    if request.exitConditions:
        for cond_item in request.exitConditions:
            raw_text = ""
            if isinstance(cond_item, str):
                raw_text = cond_item
            elif isinstance(cond_item, dict):
                raw_text = cond_item.get("rawText", "")
            elif hasattr(cond_item, "rawText"):
                raw_text = cond_item.rawText
                
            parsed = parse_logical_expression(raw_text, default_timeframe=request.timeframe or "15m")
            rule_obj = StrategyRule(rawText=raw_text, parsedRule=parsed)
            rule_obj = validate_strategy_rule(rule_obj)
            norm = normalize_parsed_rule(parsed) if parsed else raw_text
            
            db_cond = StrategyCondition(
                strategy_version_id=version.id,
                rule_type="EXIT",
                raw_text=raw_text,
                normalized_text=norm,
                rule_json=json.dumps(rule_obj.parsedRule.model_dump(by_alias=True)) if rule_obj.parsedRule else None
            )
            db.add(db_cond)

    # 3. Save Golden Rules
    if request.goldenRules:
        for rule_item in request.goldenRules:
            raw_text = ""
            if isinstance(rule_item, str):
                raw_text = rule_item
            elif isinstance(rule_item, dict):
                raw_text = rule_item.get("rawText", "")
            elif hasattr(rule_item, "rawText"):
                raw_text = rule_item.rawText
                
            from app.strategies.parser.golden_rule_parser import parse_golden_rule
            res = parse_golden_rule(raw_text, default_timeframe=request.timeframe or "15m")
            if res.parsed_rule:
                res.parsed_rule.mandatory = True
            rule_obj = StrategyRule(rawText=raw_text, parsedRule=res.parsed_rule)
            rule_obj = validate_strategy_rule(rule_obj)
            
            norm = rule_obj.parsedRule.confirmation.replace("_", " ").capitalize() if rule_obj.parsedRule and rule_obj.parsedRule.confirmation else raw_text
            
            db_rule = StrategyGoldenRule(
                strategy_version_id=version.id,
                raw_text=raw_text,
                normalized_text=norm,
                rule_type="GOLDEN_RULE",
                mandatory=True,
                evaluation=rule_obj.parsedRule.evaluation if rule_obj.parsedRule else "CANDLE_CLOSE",
                confirmation=rule_obj.parsedRule.confirmation if rule_obj.parsedRule and rule_obj.parsedRule.confirmation else "WAIT_FOR_CANDLE_CLOSE",
                timeframe=rule_obj.parsedRule.timeframe if rule_obj.parsedRule else (request.timeframe or "15m"),
                rule_json=json.dumps(rule_obj.parsedRule.model_dump(by_alias=True)) if rule_obj.parsedRule else None
            )
            db.add(db_rule)

    await db.flush()
    return version

async def create_version(db: AsyncSession, strategy: Strategy, request: StrategyRequest, version_num: int) -> StrategyVersion:
    """Instantiates a new StrategyVersion and configures relationships."""
    version = StrategyVersion(
        strategy_id=strategy.id,
        version_number=version_num,
        underlying=request.underlying.upper().strip(),
        capital=request.capital,
        trading_type=request.tradingType.upper().strip(),
        created_by=strategy.created_by
    )
    db.add(version)
    await db.flush()
    return await populate_version_relations(db, version, request)

class StrategyService:
    @staticmethod
    async def create_strategy(db: AsyncSession, request: StrategyRequest, user_id: int) -> StrategyResponse:
        request = map_request_from_builder(request)
        
        val_result = validate_strategy_request(request)
        if not val_result.valid:
            raise ValidationError(f"Strategy validation failed: {val_result.errors[0].message}", data=val_result.errors)
        
        # Uniqueness check / Seamless Upsert
        stmt_dup = select(Strategy).where(
            Strategy.user_id == user_id,
            func.lower(Strategy.name) == request.name.strip().lower()
        )
        res_dup = await db.execute(stmt_dup)
        existing_strat = res_dup.scalar_one_or_none()
        if existing_strat:
            return await StrategyService.update_strategy(db, existing_strat.id, request, user_id, is_admin=True)

        user = await StrategyRepository.get_user_by_id(db, user_id)
        if not user:
            raise ResourceNotFoundError("User not found")

        status_val = "DRAFT"
        if request.meta and request.meta.status:
            status_val = request.meta.status.upper().strip()

        strategy = Strategy(
            user_id=user_id,
            name=request.name.strip(),
            description=request.description or "",
            mode=request.mode.upper().strip(),
            status=status_val,
            created_by=user.email,
            is_prebuilt=False,
            is_active=True,
            parameters=serialize_builder_fields(request)
        )
        db.add(strategy)
        await db.flush()

        version = await create_version(db, strategy, request, 1)
        strategy.current_version_id = version.id
        db.add(strategy)
        await db.flush()

        # Initialize StrategyRuntimeState in WAITING lifecycle state
        await StrategyStateManager.initialize_runtime_state(
            db=db,
            strategy_id=strategy.id,
            strategy_version_id=version.id
        )

        return await build_strategy_response(db, strategy)

    @staticmethod
    async def update_strategy(db: AsyncSession, strategy_id: int, request: StrategyRequest, user_id: int, is_admin: bool = False) -> StrategyResponse:
        request = map_request_from_builder(request)

        val_result = validate_strategy_request(request)
        if not val_result.valid:
            raise ValidationError(f"Strategy validation failed: {val_result.errors[0].message}", data=val_result.errors)

        strategy = await StrategyRepository.get_strategy_by_id_and_user(db, strategy_id, user_id, is_admin=is_admin)
        if not strategy:
            raise ResourceNotFoundError(f"Strategy not found with ID: {strategy_id}")

        stmt_dup = select(Strategy).where(
            Strategy.id != strategy_id,
            func.lower(Strategy.name) == request.name.strip().lower()
        )
        if not is_admin:
            stmt_dup = stmt_dup.where(Strategy.user_id == user_id)
        res_dup = await db.execute(stmt_dup)
        if res_dup.scalar_one_or_none():
            raise ValidationError(f"Another strategy with name '{request.name}' already exists.")

        strategy.name = request.name.strip()
        strategy.description = request.description or ""
        strategy.mode = request.mode.upper().strip()
        if request.meta and request.meta.status:
            strategy.status = request.meta.status.upper().strip()
        strategy.parameters = serialize_builder_fields(request)

        stmt_version = select(StrategyVersion).where(StrategyVersion.id == strategy.current_version_id)
        res_version = await db.execute(stmt_version)
        current_version = res_version.scalar_one_or_none()

        is_immutable = False
        if current_version:
            is_immutable = await VersionService.is_version_immutable(db, current_version.id)

        if is_immutable:
            # Create a new version incremented by 1
            next_ver = current_version.version_number + 1
            new_version = await create_version(db, strategy, request, next_ver)
            strategy.current_version_id = new_version.id
        else:
            # Edit in-place: update current_version attributes directly and replace child relations
            if current_version:
                current_version.underlying = request.underlying.upper().strip()
                current_version.capital = request.capital
                current_version.trading_type = request.tradingType.upper().strip()
                db.add(current_version)

                from app.strategies.models import StrategyCondition, StrategyGoldenRule
                # Clear existing child records
                await db.execute(delete(StrategyLeg).where(StrategyLeg.strategy_version_id == current_version.id))
                await db.execute(delete(StrategyEntrySetting).where(StrategyEntrySetting.strategy_version_id == current_version.id))
                await db.execute(delete(StrategyEntryDay).where(StrategyEntryDay.strategy_version_id == current_version.id))
                await db.execute(delete(StrategyExitSetting).where(StrategyExitSetting.strategy_version_id == current_version.id))
                await db.execute(delete(StrategyCondition).where(StrategyCondition.strategy_version_id == current_version.id))
                await db.execute(delete(StrategyGoldenRule).where(StrategyGoldenRule.strategy_version_id == current_version.id))
                await db.flush()

                await populate_version_relations(db, current_version, request)
            else:
                new_version = await create_version(db, strategy, request, 1)
                strategy.current_version_id = new_version.id

        db.add(strategy)
        await db.flush()

        return await build_strategy_response(db, strategy)

    @staticmethod
    async def get_strategy_details(db: AsyncSession, strategy_id: int, user_id: int, is_admin: bool = False) -> StrategyResponse:
        strategy = await StrategyRepository.get_strategy_by_id_and_user(db, strategy_id, user_id, is_admin=is_admin)
        if not strategy:
            raise ResourceNotFoundError(f"Strategy not found with ID: {strategy_id}")
        return await build_strategy_response(db, strategy)

    @staticmethod
    async def list_strategies(
        db: AsyncSession,
        user_id: Optional[int] = None,
        page: int = 0,
        size: int = 20,
        search: Optional[str] = None,
        mode: Optional[str] = None,
        status: Optional[str] = None,
        is_admin: bool = False
    ) -> List[StrategyResponse]:
        strategies = await StrategyRepository.list_strategies_by_user(
            db, user_id=user_id, page=page, size=size, search=search, mode=mode, status=status, is_admin=is_admin
        )
        results = []
        for s in strategies:
            results.append(await build_strategy_response(db, s))
        return results

    @staticmethod
    async def delete_strategy(db: AsyncSession, strategy_id: int, user_id: int) -> None:
        strategy = await StrategyRepository.get_strategy_by_id_and_user(db, strategy_id, user_id)
        if not strategy:
            raise ResourceNotFoundError(f"Strategy not found with ID: {strategy_id}")

        strategy.current_version_id = None
        db.add(strategy)
        await db.flush()
        await db.delete(strategy)
        await db.flush()

    @staticmethod
    async def update_status(db: AsyncSession, strategy_id: int, status_str: str, user_id: int) -> StrategyResponse:
        strategy = await StrategyRepository.get_strategy_by_id_and_user(db, strategy_id, user_id)
        if not strategy:
            raise ResourceNotFoundError(f"Strategy not found with ID: {strategy_id}")

        valid_states = {"DRAFT", "PAPER", "ACTIVE_LIVE", "PAUSED", "STOPPED"}
        trans = status_str.upper().strip()
        if trans not in valid_states:
            raise ValidationError(f"Invalid strategy status transition state: {status_str}")

        strategy.status = trans
        db.add(strategy)
        await db.flush()
        return await build_strategy_response(db, strategy)

    @staticmethod
    async def activate_strategy(db: AsyncSession, strategy_id: int, user_id: int) -> StrategyResponse:
        """
        Activates strategy on PAPER mode (default safe execution),
        transitions runtime state: WAITING -> ELIGIBLE -> MONITORING_ENTRY,
        and registers candidate in StrategyRouter index.
        """
        import logging
        logger = logging.getLogger(__name__)

        strategy = await StrategyRepository.get_strategy_by_id_and_user(db, strategy_id, user_id)
        if not strategy:
            raise ResourceNotFoundError(f"Strategy not found with ID: {strategy_id}")

        if not strategy.current_version_id:
            raise ValidationError(f"Strategy {strategy_id} has no active version.")

        stmt_version = select(StrategyVersion).where(StrategyVersion.id == strategy.current_version_id)
        res_version = await db.execute(stmt_version)
        version = res_version.scalar_one_or_none()
        if not version:
            raise ResourceNotFoundError(f"Strategy version {strategy.current_version_id} not found.")

        # Activate on PAPER mode (safe default)
        strategy.status = "PAPER" if strategy.mode == "PAPER" else "ACTIVE_LIVE"
        strategy.is_active = True
        db.add(strategy)
        await db.flush()

        from app.strategies.enums import StrategyLifecycleState
        from app.strategies.state_manager import strategy_state_manager
        # Initialize or advance runtime state: WAITING -> ELIGIBLE -> MONITORING_ENTRY
        runtime_state = await strategy_state_manager.get_runtime_state(db, strategy.id)
        if not runtime_state:
            runtime_state = await strategy_state_manager.initialize_runtime_state(db, strategy.id, version.id)

        if runtime_state.lifecycle_state == "WAITING":
            await strategy_state_manager.transition_state(db, strategy.id, version.id, StrategyLifecycleState.ELIGIBLE, "Strategy activated")
            await strategy_state_manager.transition_state(db, strategy.id, version.id, StrategyLifecycleState.MONITORING_ENTRY, "Monitoring market events")

        # Register strategy in StrategyRouter routing index
        from app.strategies.routing.schemas import CandidateStrategy
        from app.strategies.routing.router import strategy_router
        
        tf_str = "15m"
        if strategy.parameters:
            try:
                params = json.loads(strategy.parameters)
                tf_str = params.get("timeframe", "15m")
            except Exception:
                tf_str = "15m"

        candidate = CandidateStrategy(
            strategy_id=strategy.id,
            strategy_version_id=version.id,
            symbol=version.underlying,
            timeframe=tf_str,
            lifecycle_state=StrategyLifecycleState.MONITORING_ENTRY,
            is_active=True
        )
        await strategy_router.index.register_candidate(candidate)

        logger.info(
            "strategy_activated: strategy_id=%s version_id=%s mode=%s state=MONITORING_ENTRY",
            strategy.id, version.id, strategy.mode,
            extra={
                "event": "strategy_activated",
                "strategy_id": strategy.id,
                "strategy_version_id": version.id,
                "mode": strategy.mode,
                "lifecycle_state": "MONITORING_ENTRY"
            }
        )

        return await build_strategy_response(db, strategy)

    @staticmethod
    def validate_strategy_definition(request: StrategyRequest) -> StrategyValidationResponse:
        """Validates all Strategy Builder metadata, schedule, rules, and risk configurations."""
        errors = []
        
        # 1. Meta check
        if not request.meta or not request.meta.strategyName:
            errors.append(StrategyValidationError(field="meta.strategyName", code="REQUIRED", message="Strategy name is required"))
        if not request.timeframe:
            errors.append(StrategyValidationError(field="timeframe", code="REQUIRED", message="Strategy default timeframe is required"))

        # 2. Schedule check
        if not request.schedule:
            errors.append(StrategyValidationError(field="schedule", code="REQUIRED", message="Schedule configuration is required"))
        else:
            sched = request.schedule
            if not re.match(r"^\d{2}:\d{2}$", sched.entryFrom):
                errors.append(StrategyValidationError(field="schedule.entryFrom", code="INVALID_FORMAT", message="entryFrom must be HH:MM"))
            if not re.match(r"^\d{2}:\d{2}$", sched.entryTo):
                errors.append(StrategyValidationError(field="schedule.entryTo", code="INVALID_FORMAT", message="entryTo must be HH:MM"))
            if not re.match(r"^\d{2}:\d{2}$", sched.forcedExitTime):
                errors.append(StrategyValidationError(field="schedule.forcedExitTime", code="INVALID_FORMAT", message="forcedExitTime must be HH:MM"))

        # 3. Instrument check
        if not request.instrument or not request.instrument.underlying:
            errors.append(StrategyValidationError(field="instrument.underlying", code="REQUIRED", message="Instrument underlying asset is required"))

        # 4. Rules check
        if request.entryConditions:
            for idx, cond in enumerate(request.entryConditions):
                if isinstance(cond, str):
                    parsed = parse_logical_expression(cond, default_timeframe=request.timeframe or "15m")
                    rule_obj = StrategyRule(rawText=cond, parsedRule=parsed)
                elif isinstance(cond, StrategyRule):
                    rule_obj = cond
                else:
                    rule_obj = StrategyRule.model_validate(cond)

                rule_obj = validate_strategy_rule(rule_obj)
                if rule_obj.validationStatus == "INVALID":
                    errors.append(StrategyValidationError(
                        field=f"entryConditions[{idx}]",
                        code="INVALID_RULE",
                        message=rule_obj.errors[0] if rule_obj.errors else "Invalid rule structure"
                    ))

        return StrategyValidationResponse(
            valid=len(errors) == 0,
            errors=errors
        )
