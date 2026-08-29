from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from app.subscriptions.models import Plan, PlanStrategyAccess
from app.core.exceptions import ResourceNotFoundError, DuplicateRequestException

async def create_plan(db: AsyncSession, request) -> Plan:
    """Creates a new subscription plan."""
    # Check uniqueness
    stmt = select(Plan).where(Plan.code == request.code)
    res = await db.execute(stmt)
    if res.scalar_one_or_none():
        raise DuplicateRequestException(f"Plan with code '{request.code}' already exists")

    plan = Plan(
        code=request.code,
        name=request.name,
        description=request.description,
        monthly_price=request.monthlyPrice,
        currency="INR",
        gst_percentage=request.gstPercentage,
        min_wallet_balance=request.minWalletBalance,
        max_active_strategies=request.maxActiveStrategies,
        max_strategy_executions_per_day=request.maxStrategyExecutionsPerDay,
        max_portfolio_capital=request.maxPortfolioCapital,
        subscription_type=request.subscriptionType,
        is_active=True
    )
    db.add(plan)
    await db.flush()
    return plan

async def get_active_plans(db: AsyncSession) -> List[Plan]:
    """Lists all active plans."""
    stmt = select(Plan).where(Plan.is_active == True).order_by(Plan.display_order.asc(), Plan.id.asc())
    res = await db.execute(stmt)
    return list(res.scalars().all())

async def get_plan_details(db: AsyncSession, plan_id: int) -> Plan:
    """Finds a plan by ID or raises 404."""
    stmt = select(Plan).where(Plan.id == plan_id)
    res = await db.execute(stmt)
    plan = res.scalar_one_or_none()
    if not plan:
        raise ResourceNotFoundError(f"Plan not found with ID: {plan_id}")
    return plan

async def update_plan(db: AsyncSession, plan_id: int, request) -> Plan:
    """Updates properties of a plan."""
    plan = await get_plan_details(db, plan_id)
    
    # Uniqueness check on code
    if request.code != plan.code:
        stmt = select(Plan).where(Plan.code == request.code)
        res = await db.execute(stmt)
        if res.scalar_one_or_none():
            raise DuplicateRequestException(f"Plan with code '{request.code}' already exists")

    plan.code = request.code
    plan.name = request.name
    plan.description = request.description
    plan.monthly_price = request.monthlyPrice
    plan.gst_percentage = request.gstPercentage
    plan.min_wallet_balance = request.minWalletBalance
    plan.max_active_strategies = request.maxActiveStrategies
    plan.max_strategy_executions_per_day = request.maxStrategyExecutionsPerDay
    plan.max_portfolio_capital = request.maxPortfolioCapital
    plan.subscription_type = request.subscriptionType
    
    db.add(plan)
    await db.flush()
    return plan

async def delete_plan(db: AsyncSession, plan_id: int) -> None:
    """Deletes a plan."""
    plan = await get_plan_details(db, plan_id)
    await db.delete(plan)
    await db.flush()

async def set_plan_active_status(db: AsyncSession, plan_id: int, active: bool) -> Plan:
    """Activates or deactivates a plan."""
    plan = await get_plan_details(db, plan_id)
    plan.is_active = active
    db.add(plan)
    await db.flush()
    return plan

async def get_mapped_strategies(db: AsyncSession, plan_id: int) -> List[int]:
    """Retrieves all strategy IDs mapped to a plan."""
    stmt = select(PlanStrategyAccess.strategy_id).where(
        PlanStrategyAccess.plan_id == plan_id,
        PlanStrategyAccess.is_enabled == True
    )
    res = await db.execute(stmt)
    return list(res.scalars().all())

async def map_strategy_to_plan(db: AsyncSession, plan_id: int, strategy_id: int) -> None:
    """Maps a strategy to a plan (with unique constraint logic)."""
    # Check if access already exists
    stmt = select(PlanStrategyAccess).where(
        PlanStrategyAccess.plan_id == plan_id,
        PlanStrategyAccess.strategy_id == strategy_id
    )
    res = await db.execute(stmt)
    access = res.scalar_one_or_none()

    if access:
        access.is_enabled = True
        db.add(access)
    else:
        # Import to prevent circular dependencies
        from app.strategies.models import Strategy
        # Verify strategy exists
        stmt_strat = select(Strategy).where(Strategy.id == strategy_id)
        res_strat = await db.execute(stmt_strat)
        if not res_strat.scalar_one_or_none():
            raise ResourceNotFoundError(f"Strategy not found with ID: {strategy_id}")
            
        access = PlanStrategyAccess(
            plan_id=plan_id,
            strategy_id=strategy_id,
            is_enabled=True
        )
        db.add(access)
    await db.flush()

async def update_strategy_mapping(db: AsyncSession, plan_id: int, strategy_id: int, enabled: bool) -> None:
    """Toggles status on a strategy-to-plan mapping."""
    stmt = select(PlanStrategyAccess).where(
        PlanStrategyAccess.plan_id == plan_id,
        PlanStrategyAccess.strategy_id == strategy_id
    )
    res = await db.execute(stmt)
    access = res.scalar_one_or_none()
    if not access:
        raise ResourceNotFoundError("Mapping not found")
    access.is_enabled = enabled
    db.add(access)
    await db.flush()

async def delete_strategy_mapping(db: AsyncSession, plan_id: int, strategy_id: int) -> None:
    """Deletes mapping completely."""
    stmt = select(PlanStrategyAccess).where(
        PlanStrategyAccess.plan_id == plan_id,
        PlanStrategyAccess.strategy_id == strategy_id
    )
    res = await db.execute(stmt)
    access = res.scalar_one_or_none()
    if not access:
        raise ResourceNotFoundError("Mapping not found")
    await db.delete(access)
    await db.flush()
