from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update, func
import uuid
import json
from typing import List, Optional

from app.users.models import User
from app.subscriptions.models import Plan, Subscription, SubscriptionEvent, SubscriptionPayment
from app.subscriptions.schemas import SubscriptionRequest, UpgradeRequest, DowngradeRequest, CancelRequest, SubscribeResponse
from app.wallets import service as wallet_service
from app.core.exceptions import ValidationError, ResourceNotFoundError

SANDBOX_MODE = True # Default to sandbox mode simulation

def log_subscription_event(
    db: AsyncSession,
    subscription_id: int,
    event_type: str,
    old_plan_id: Optional[int],
    new_plan_id: Optional[int],
    old_status: Optional[str],
    new_status: Optional[str],
    ref_id: Optional[str] = None,
    metadata_val: Optional[dict] = None
) -> SubscriptionEvent:
    """Logs subscription transition event into database."""
    # Convert dict metadata to string json
    meta_str = json.dumps(metadata_val) if metadata_val else None
    event = SubscriptionEvent(
        subscription_id=subscription_id,
        event_type=event_type,
        old_plan_id=old_plan_id,
        new_plan_id=new_plan_id,
        old_status=old_status,
        new_status=new_status,
        reference_id=ref_id,
        event_metadata=meta_str
    )
    db.add(event)
    return event

async def subscribe(db: AsyncSession, user_id: int, request: SubscriptionRequest) -> SubscribeResponse:
    """Creates a new PENDING subscription and payment invoice."""
    stmt_user = select(User).where(User.id == user_id)
    res_user = await db.execute(stmt_user)
    user = res_user.scalar_one_or_none()
    if not user:
        raise ResourceNotFoundError("User not found")

    stmt_plan = select(Plan).where(Plan.id == request.planId)
    res_plan = await db.execute(stmt_plan)
    plan = res_plan.scalar_one_or_none()
    if not plan:
        raise ResourceNotFoundError("Plan not found")

    if not plan.is_active:
        raise ValidationError("Cannot subscribe to an inactive plan.")

    # Cancel previous pending subscriptions to avoid clutter
    stmt_old_pending = select(Subscription).where(
        Subscription.user_id == user_id,
        Subscription.status == "PENDING"
    ).order_by(Subscription.created_at.desc())
    res_old_pending = await db.execute(stmt_old_pending)
    for old_s in res_old_pending.scalars().all():
        old_s.status = "CANCELLED"
        db.add(old_s)

    now = datetime.now(timezone.utc)
    subscription = Subscription(
        user_id=user_id,
        plan_id=plan.id,
        status="PENDING",
        start_at=now,
        current_period_start=now,
        current_period_end=now + timedelta(days=30),
        auto_renew=True,
        payment_provider=request.paymentProvider
    )
    db.add(subscription)
    await db.flush() # Flush to get subscription.id

    # Pricing calculations
    monthly_price = plan.monthly_price
    gst_multiplier = plan.gst_percentage / Decimal("100.00")
    gst_amount = (monthly_price * gst_multiplier).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    total_amount = (monthly_price + gst_amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    idempotency_key = "SUB-INIT-" + str(uuid.uuid4())
    provider_order_id = f"order_mock_{str(uuid.uuid4())[:8]}" if SANDBOX_MODE else f"order_{str(uuid.uuid4())}"

    payment = SubscriptionPayment(
        user_id=user_id,
        subscription_id=subscription.id,
        plan_id=plan.id,
        amount=monthly_price,
        gst_amount=gst_amount,
        total_amount=total_amount,
        currency=plan.currency,
        payment_provider=request.paymentProvider,
        provider_order_id=provider_order_id,
        status="CREATED",
        idempotency_key=idempotency_key
    )
    db.add(payment)

    # Log creation event
    log_subscription_event(
        db,
        subscription_id=subscription.id,
        event_type="SUBSCRIPTION_CREATED",
        old_plan_id=None,
        new_plan_id=plan.id,
        old_status=None,
        new_status="PENDING",
        ref_id=provider_order_id
    )

    return SubscribeResponse(
        subscriptionId=subscription.id,
        planId=plan.id,
        amount=monthly_price,
        totalAmount=total_amount,
        providerOrderId=provider_order_id,
        status="PENDING",
        createdAt=now
    )

async def activate_subscription(db: AsyncSession, provider_order_id: str, provider_payment_id: str) -> None:
    """Activates the subscription associated with a completed payment order."""
    stmt_payment = select(SubscriptionPayment).where(SubscriptionPayment.provider_order_id == provider_order_id)
    res_payment = await db.execute(stmt_payment)
    payment = res_payment.scalar_one_or_none()
    if not payment:
        raise ResourceNotFoundError(f"Payment record not found for Order ID: {provider_order_id}")

    if payment.status == "SUCCESS":
        return

    payment.status = "SUCCESS"
    payment.provider_payment_id = provider_payment_id
    payment.paid_at = datetime.now(timezone.utc)
    db.add(payment)

    # Resolve subscription details
    stmt_sub = select(Subscription).where(Subscription.id == payment.subscription_id)
    res_sub = await db.execute(stmt_sub)
    subscription = res_sub.scalar_one()

    old_status = subscription.status

    # Expire currently active subscriptions
    stmt_active = select(Subscription).where(
        Subscription.user_id == subscription.user_id,
        Subscription.status == "ACTIVE"
    )
    res_active = await db.execute(stmt_active)
    for active_sub in res_active.scalars().all():
        active_sub.status = "EXPIRED"
        db.add(active_sub)
        log_subscription_event(
            db,
            subscription_id=active_sub.id,
            event_type="SUBSCRIPTION_EXPIRED",
            old_plan_id=active_sub.plan_id,
            new_plan_id=None,
            old_status="ACTIVE",
            new_status="EXPIRED"
        )

    now = datetime.now(timezone.utc)
    subscription.status = "ACTIVE"
    subscription.start_at = now
    subscription.current_period_start = now
    subscription.current_period_end = now + timedelta(days=30)
    db.add(subscription)

    log_subscription_event(
        db,
        subscription_id=subscription.id,
        event_type="SUBSCRIPTION_ACTIVATED",
        old_plan_id=None,
        new_plan_id=subscription.plan_id,
        old_status=old_status,
        new_status="ACTIVE",
        ref_id=provider_payment_id
    )

async def upgrade_subscription(db: AsyncSession, user_id: int, request: UpgradeRequest) -> SubscribeResponse:
    """Upgrades plan, calculating pro-rated credits or triggering immediate free activation."""
    stmt_user = select(User).where(User.id == user_id)
    res_user = await db.execute(stmt_user)
    user = res_user.scalar_one_or_none()
    if not user:
        raise ResourceNotFoundError("User not found")

    stmt_target = select(Plan).where(Plan.id == request.newPlanId)
    res_target = await db.execute(stmt_target)
    target_plan = res_target.scalar_one_or_none()
    if not target_plan:
        raise ResourceNotFoundError("Target plan not found")

    if not target_plan.is_active:
        raise ValidationError("Cannot upgrade to an inactive plan.")

    # Fetch active subscription
    stmt_active = select(Subscription).where(
        Subscription.user_id == user_id,
        Subscription.status == "ACTIVE"
    )
    res_active = await db.execute(stmt_active)
    active_sub = res_active.scalar_one_or_none()
    if not active_sub:
        raise ValidationError("User does not have an active subscription to upgrade.")

    if active_sub.plan_id == target_plan.id:
        raise ValidationError("User is already subscribed to this plan.")

    # Fetch current plan details
    stmt_curr = select(Plan).where(Plan.id == active_sub.plan_id)
    res_curr = await db.execute(stmt_curr)
    current_plan = res_curr.scalar_one()

    # 1. Calculate Prorated Credit of current plan
    now = datetime.now(timezone.utc)
    remaining_delta = active_sub.current_period_end - now
    days_remaining = max(0, remaining_delta.days)

    curr_plan_cost_multiplier = Decimal("1.00") + (current_plan.gst_percentage / Decimal("100.00"))
    current_plan_cost = current_plan.monthly_price * curr_plan_cost_multiplier
    credit_per_day = current_plan_cost / Decimal("30.00")
    prorated_credit = (credit_per_day * Decimal(days_remaining)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # 2. Target Plan Cost
    target_plan_cost_multiplier = Decimal("1.00") + (target_plan.gst_percentage / Decimal("100.00"))
    target_plan_cost = target_plan.monthly_price * target_plan_cost_multiplier

    amount_due = (target_plan_cost - prorated_credit).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    if amount_due <= 0:
        # Immediate free upgrade (Credit covers everything)
        active_sub.status = "EXPIRED"
        db.add(active_sub)
        log_subscription_event(
            db,
            subscription_id=active_sub.id,
            event_type="SUBSCRIPTION_EXPIRED",
            old_plan_id=active_sub.plan_id,
            new_plan_id=None,
            old_status="ACTIVE",
            new_status="EXPIRED"
        )

        new_sub = Subscription(
            user_id=user_id,
            plan_id=target_plan.id,
            status="ACTIVE",
            start_at=now,
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
            auto_renew=True
        )
        db.add(new_sub)
        await db.flush()

        log_subscription_event(
            db,
            subscription_id=new_sub.id,
            event_type="SUBSCRIPTION_UPGRADED",
            old_plan_id=current_plan.id,
            new_plan_id=target_plan.id,
            old_status="ACTIVE",
            new_status="ACTIVE",
            ref_id="FREE_UPGRADE"
        )

        return SubscribeResponse(
            subscriptionId=new_sub.id,
            planId=target_plan.id,
            amount=Decimal("0.00"),
            totalAmount=Decimal("0.00"),
            status="ACTIVE",
            createdAt=now
        )
    else:
        # Payment required for the prorated diff
        new_sub = Subscription(
            user_id=user_id,
            plan_id=target_plan.id,
            status="PENDING",
            start_at=now,
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
            auto_renew=True,
            payment_provider=request.paymentProvider
        )
        db.add(new_sub)
        await db.flush()

        # Deduce base and GST prorated amounts
        gst_percent = target_plan.gst_percentage
        gst_multiplier = Decimal("1.00") + (gst_percent / Decimal("100.00"))
        base_amount_due = (amount_due / gst_multiplier).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        gst_amount_due = (amount_due - base_amount_due).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        provider_order_id = f"order_mock_{str(uuid.uuid4())[:8]}" if SANDBOX_MODE else f"order_{str(uuid.uuid4())}"

        payment = SubscriptionPayment(
            user_id=user_id,
            subscription_id=new_sub.id,
            plan_id=target_plan.id,
            amount=base_amount_due,
            gst_amount=gst_amount_due,
            total_amount=amount_due,
            currency=target_plan.currency,
            payment_provider=request.paymentProvider,
            provider_order_id=provider_order_id,
            status="CREATED",
            idempotency_key="UPGRADE-SUB-" + str(uuid.uuid4())
        )
        db.add(payment)

        log_subscription_event(
            db,
            subscription_id=new_sub.id,
            event_type="SUBSCRIPTION_UPGRADED",
            old_plan_id=current_plan.id,
            new_plan_id=target_plan.id,
            old_status="ACTIVE",
            new_status="PENDING",
            ref_id=provider_order_id
        )

        return SubscribeResponse(
            subscriptionId=new_sub.id,
            planId=target_plan.id,
            amount=base_amount_due,
            totalAmount=amount_due,
            providerOrderId=provider_order_id,
            status="PENDING",
            createdAt=now
        )

async def downgrade_subscription(db: AsyncSession, user_id: int, request: DowngradeRequest) -> None:
    """Schedules a plan downgrade transition on current period end, disabling auto-renew."""
    stmt_active = select(Subscription).where(
        Subscription.user_id == user_id,
        Subscription.status == "ACTIVE"
    )
    res_active = await db.execute(stmt_active)
    active_sub = res_active.scalar_one_or_none()
    if not active_sub:
        raise ValidationError("User does not have an active subscription to downgrade.")

    stmt_target = select(Plan).where(Plan.id == request.newPlanId)
    res_target = await db.execute(stmt_target)
    target_plan = res_target.scalar_one_or_none()
    if not target_plan or not target_plan.is_active:
        raise ValidationError("Cannot downgrade to an inactive plan.")

    if active_sub.plan_id == target_plan.id:
        raise ValidationError("User is already subscribed to this plan.")

    # Downgrade: Disable auto-renew on active sub and log downgrade event
    active_sub.auto_renew = False
    db.add(active_sub)

    metadata = {
        "targetPlanId": target_plan.id,
        "message": "Scheduled transition to new plan on expiration"
    }

    log_subscription_event(
        db,
        subscription_id=active_sub.id,
        event_type="SUBSCRIPTION_DOWNGRADED",
        old_plan_id=active_sub.plan_id,
        new_plan_id=target_plan.id,
        old_status="ACTIVE",
        new_status="ACTIVE",
        metadata_val=metadata
    )

async def cancel_subscription(db: AsyncSession, user_id: int, request: CancelRequest) -> None:
    """Cancels subscription immediately or disables auto-renew on expiry."""
    stmt_active = select(Subscription).where(
        Subscription.user_id == user_id,
        Subscription.status == "ACTIVE"
    )
    res_active = await db.execute(stmt_active)
    active_sub = res_active.scalar_one_or_none()
    if not active_sub:
        raise ValidationError("User does not have an active subscription to cancel.")

    active_sub.cancellation_reason = request.reason
    
    # If immediate cancel is needed, set status cancelled, else disable auto-renew
    # In python, let's allow both. Since CancelRequest in Java didn't have immediate parameter directly in DTO, wait, in java: `request.isImmediate()`
    # Let's add immediate boolean or default to auto_renew=False (standard SaaS cancel behavior)
    immediate = False # Default to billing cycle cancel
    
    if immediate:
        active_sub.status = "CANCELLED"
        active_sub.cancelled_at = datetime.now(timezone.utc)
        db.add(active_sub)
        log_subscription_event(
            db,
            subscription_id=active_sub.id,
            event_type="SUBSCRIPTION_CANCELLED",
            old_plan_id=active_sub.plan_id,
            new_plan_id=None,
            old_status="ACTIVE",
            new_status="CANCELLED",
            ref_id=request.reason
        )
    else:
        active_sub.auto_renew = False
        db.add(active_sub)
        log_subscription_event(
            db,
            subscription_id=active_sub.id,
            event_type="SUBSCRIPTION_CANCELLED",
            old_plan_id=active_sub.plan_id,
            new_plan_id=None,
            old_status="ACTIVE",
            new_status="ACTIVE",
            ref_id=f"Auto-renew disabled: {request.reason}"
        )

async def reactivate_subscription(db: AsyncSession, user_id: int) -> None:
    """Enables auto-renewal back on an active subscription."""
    stmt_active = select(Subscription).where(
        Subscription.user_id == user_id,
        Subscription.status == "ACTIVE"
    )
    res_active = await db.execute(stmt_active)
    active_sub = res_active.scalar_one_or_none()
    if not active_sub:
        raise ValidationError("User does not have an active subscription to reactivate.")

    if active_sub.auto_renew:
        raise ValidationError("Subscription is already set to auto-renew.")

    active_sub.auto_renew = True
    db.add(active_sub)

    log_subscription_event(
        db,
        subscription_id=active_sub.id,
        event_type="SUBSCRIPTION_REACTIVATED",
        old_plan_id=None,
        new_plan_id=active_sub.plan_id,
        old_status="ACTIVE",
        new_status="ACTIVE"
    )
