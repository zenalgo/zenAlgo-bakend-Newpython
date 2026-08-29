from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete, func, exists
from typing import List, Optional
from decimal import Decimal
from sqlalchemy.orm.attributes import set_committed_value

from app.users.models import User
from app.strategies.models import (
    Strategy, StrategyVersion, StrategyLeg,
    StrategyEntrySetting, StrategyEntryDay, StrategyExitSetting, StrategyExecution
)
from app.strategies.schemas import StrategyRequest, StrategyResponse, StrategyLegResponse, StrategyEntrySettingResponse, StrategyExitSettingResponse
from app.strategies.validator import validate_strategy_request
from app.core.exceptions import ValidationError, ResourceNotFoundError, AuthorizationError

async def map_version_to_response_dict(version: StrategyVersion) -> dict:
    """Helper to convert active version configuration relationships to dict fields."""
    legs = []
    for leg in version.legs:
        legs.append({
            "id": leg.id,
            "sequence": leg.sequence,
            "segment": leg.segment,
            "side": leg.side,
            "strikeSelection": leg.strike_selection,
            "strikeValue": leg.strike_value,
            "expiry": leg.expiry,
            "lots": leg.lots,
            "targetType": leg.target_type,
            "targetValue": leg.target_value,
            "stopLossType": leg.stop_loss_type,
            "stopLossValue": leg.stop_loss_value,
            "trailingSlEnabled": leg.trailing_sl_enabled,
            "trailingSlActivateType": leg.trailing_sl_activate_type,
            "trailingSlActivateValue": leg.trailing_sl_activate_value,
            "trailingSlIncreaseBy": leg.trailing_sl_increase_by,
            "trailingSlBy": leg.trailing_sl_by
        })

    entry_setting = {
        "entryTime": version.entry_setting.entry_time if version.entry_setting else "09:15"
    }

    entry_days = [day.day_of_week for day in version.entry_days]

    exit_setting = {
        "profitMtmType": version.exit_setting.profit_mtm_type if version.exit_setting else "NONE",
        "profitMtmValue": version.exit_setting.profit_mtm_value if version.exit_setting else None,
        "stopLossMtmType": version.exit_setting.stop_loss_mtm_type if version.exit_setting else "NONE",
        "stopLossMtmValue": version.exit_setting.stop_loss_mtm_value if version.exit_setting else None,
        "exitTime": version.exit_setting.exit_time if version.exit_setting else "15:15",
        "exitOnExpiry": version.exit_setting.exit_on_expiry if version.exit_setting else True,
        "exitAfterEntryType": version.exit_setting.exit_after_entry_type if version.exit_setting else "NONE",
        "exitAfterEntryValue": version.exit_setting.exit_after_entry_value if version.exit_setting else None
    }

    return {
        "versionNumber": version.version_number,
        "underlying": version.underlying,
        "capital": version.capital,
        "tradingType": version.trading_type,
        "legs": legs,
        "entrySetting": entry_setting,
        "entryDays": entry_days,
        "exitSetting": exit_setting
    }

async def build_strategy_response(db: AsyncSession, strategy: Strategy) -> StrategyResponse:
    """Loads current version relationships and maps Strategy to StrategyResponse DTO."""
    # Eager load version
    stmt = select(StrategyVersion).where(StrategyVersion.id == strategy.current_version_id)
    res = await db.execute(stmt)
    version = res.scalar_one_or_none()

    if not version:
        return StrategyResponse(
            id=strategy.id,
            userId=strategy.user_id,
            name=strategy.name,
            description=strategy.description,
            status=strategy.status,
            mode=strategy.mode,
            versionNumber=0,
            underlying="",
            capital=Decimal("0.00"),
            tradingType="INTRADAY",
            legs=[],
            entrySetting={"entryTime": "09:15"},
            entryDays=[],
            exitSetting={"entryTime": "15:15"}
        )

    # Resolve relationships using set_committed_value to bypass lazy loads
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

    v_data = await map_version_to_response_dict(version)

    return StrategyResponse(
        id=strategy.id,
        userId=strategy.user_id,
        name=strategy.name,
        description=strategy.description,
        status=strategy.status,
        mode=strategy.mode,
        versionNumber=v_data["versionNumber"],
        underlying=v_data["underlying"],
        capital=v_data["capital"],
        tradingType=v_data["tradingType"],
        legs=[StrategyLegResponse.model_validate(leg) for leg in v_data["legs"]],
        entrySetting=StrategyEntrySettingResponse.model_validate(v_data["entrySetting"]),
        entryDays=v_data["entryDays"],
        exitSetting=StrategyExitSettingResponse.model_validate(v_data["exitSetting"])
    )

async def create_version(db: AsyncSession, strategy: Strategy, request: StrategyRequest, version_num: int) -> StrategyVersion:
    """Helper method to instantiate a new StrategyVersion and sub-configurations."""
    version = StrategyVersion(
        strategy_id=strategy.id,
        version_number=version_num,
        underlying=request.underlying.upper().strip(),
        capital=request.capital,
        trading_type=request.tradingType.upper().strip(),
        created_by=strategy.created_by
    )
    db.add(version)
    await db.flush() # Flush to get version.id

    # 1. Position Legs
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

    # 2. Entry Settings & Days
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

    # 3. Exit Settings
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

    await db.flush()
    return version

async def create_strategy(db: AsyncSession, request: StrategyRequest, user_id: int) -> StrategyResponse:
    """Validates parameters, creates strategy record and Version 1 child models."""
    val_result = validate_strategy_request(request)
    if not val_result.valid:
        raise ValidationError(f"Strategy validation failed: {val_result.errors[0].message}", data=val_result.errors)

    # Name uniqueness check for user
    stmt_user = select(User).where(User.id == user_id)
    res_user = await db.execute(stmt_user)
    user = res_user.scalar_one_or_none()
    if not user:
        raise ResourceNotFoundError("User not found")

    stmt_dup = select(Strategy).where(
        Strategy.user_id == user_id,
        func.lower(Strategy.name) == request.name.strip().lower()
    )
    res_dup = await db.execute(stmt_dup)
    if res_dup.scalar_one_or_none():
        raise ValidationError(f"A strategy with name '{request.name}' already exists.")

    strategy = Strategy(
        user_id=user_id,
        name=request.name.strip(),
        description=request.description,
        mode=request.mode.upper().strip(),
        status="DRAFT",
        created_by=user.email,
        is_prebuilt=False,
        is_active=True
    )
    db.add(strategy)
    await db.flush()

    # Create version 1
    version = await create_version(db, strategy, request, 1)

    strategy.current_version_id = version.id
    db.add(strategy)
    await db.flush()

    return await build_strategy_response(db, strategy)

async def update_strategy(db: AsyncSession, strategy_id: int, request: StrategyRequest, user_id: int) -> StrategyResponse:
    """Modifies properties, triggering Version N+1 if active executions exist or editing in-place if not."""
    val_result = validate_strategy_request(request)
    if not val_result.valid:
        raise ValidationError(f"Strategy validation failed: {val_result.errors[0].message}", data=val_result.errors)

    stmt_strat = select(Strategy).where(Strategy.id == strategy_id, Strategy.user_id == user_id)
    res_strat = await db.execute(stmt_strat)
    strategy = res_strat.scalar_one_or_none()
    if not strategy:
        raise ResourceNotFoundError(f"Strategy not found with ID: {strategy_id}")

    # Name duplicate check excluding current strategy
    stmt_dup = select(Strategy).where(
        Strategy.user_id == user_id,
        Strategy.id != strategy_id,
        func.lower(Strategy.name) == request.name.strip().lower()
    )
    res_dup = await db.execute(stmt_dup)
    if res_dup.scalar_one_or_none():
        raise ValidationError(f"Another strategy with name '{request.name}' already exists.")

    strategy.name = request.name.strip()
    strategy.description = request.description
    strategy.mode = request.mode.upper().strip()

    # Fetch current version
    stmt_version = select(StrategyVersion).where(StrategyVersion.id == strategy.current_version_id)
    res_version = await db.execute(stmt_version)
    current_version = res_version.scalar_one_or_none()

    has_executions = False
    if current_version:
        # Check executions
        stmt_exec_exists = select(exists().where(StrategyExecution.strategy_version_id == current_version.id))
        res_exec_exists = await db.execute(stmt_exec_exists)
        has_executions = res_exec_exists.scalar()

    if has_executions:
        # Immutable versioning: create a new version incremented by 1
        next_ver = current_version.version_number + 1
        new_version = await create_version(db, strategy, request, next_ver)
        strategy.current_version_id = new_version.id
    else:
        # Inplace edit: delete previous version config and write new setup
        if current_version:
            # Nullify FK constraint first to avoid FK error on deletion
            strategy.current_version_id = None
            db.add(strategy)
            await db.flush()
            
            # Delete old version configuration (cascades will delete legs, days, entry, exit)
            await db.delete(current_version)
            await db.flush()

        new_version = await create_version(db, strategy, request, current_version.version_number if current_version else 1)
        strategy.current_version_id = new_version.id

    db.add(strategy)
    await db.flush()

    return await build_strategy_response(db, strategy)

async def get_my_strategies(db: AsyncSession, user_id: int) -> List[StrategyResponse]:
    """Retrieves all strategies owned by a user."""
    stmt = select(Strategy).where(Strategy.user_id == user_id).order_by(Strategy.id.desc())
    res = await db.execute(stmt)
    strategies = res.scalars().all()
    
    results = []
    for s in strategies:
        results.append(await build_strategy_response(db, s))
    return results

async def get_strategy_details(db: AsyncSession, strategy_id: int, user_id: int) -> StrategyResponse:
    """Retrieves a strategy by user id and strategy id."""
    stmt = select(Strategy).where(Strategy.id == strategy_id, Strategy.user_id == user_id)
    res = await db.execute(stmt)
    strategy = res.scalar_one_or_none()
    if not strategy:
        raise ResourceNotFoundError(f"Strategy not found with ID: {strategy_id}")
    return await build_strategy_response(db, strategy)

async def delete_strategy(db: AsyncSession, strategy_id: int, user_id: int) -> None:
    """Deletes a strategy and its mappings."""
    stmt = select(Strategy).where(Strategy.id == strategy_id, Strategy.user_id == user_id)
    res = await db.execute(stmt)
    strategy = res.scalar_one_or_none()
    if not strategy:
        raise ResourceNotFoundError(f"Strategy not found with ID: {strategy_id}")

    # Nullify current version relation first
    strategy.current_version_id = None
    db.add(strategy)
    await db.flush()

    # Delete strategy (cascades versioning, legs, etc.)
    await db.delete(strategy)
    await db.flush()

async def update_status(db: AsyncSession, strategy_id: int, status_str: str, user_id: int) -> StrategyResponse:
    """Transitions strategy lifecycle status, verifying validation constraints."""
    stmt = select(Strategy).where(Strategy.id == strategy_id, Strategy.user_id == user_id)
    res = await db.execute(stmt)
    strategy = res.scalar_one_or_none()
    if not strategy:
        raise ResourceNotFoundError(f"Strategy not found with ID: {strategy_id}")

    if status_str.upper() == "ACTIVE_LIVE":
        if strategy.current_version_id is None:
            raise ValidationError("Strategy cannot be activated without an active version configuration.")

    strategy.status = status_str.upper().strip()
    db.add(strategy)
    await db.flush()
    return await build_strategy_response(db, strategy)
