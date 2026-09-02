import pytz
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, desc

from app.users.models import User, UserRole
from app.subscriptions.models import (
    AdminPaymentMethod,
    Subscription,
    SubscriptionPayment,
    SubscriptionEvent,
    Plan,
)
from app.wallets.models import Wallet, WalletTransaction
from app.subscriptions.schemas import (
    AdminPaymentMethodRequest,
    AdminPaymentMethodResponse,
    PlanPurchaseRequest,
    PendingSubscriptionRequestResponse,
    AdminPlanWalletLedgerResponse,
    PlanWalletLedgerItem,
)
from app.core.exceptions import ResourceNotFoundError, ValidationError

class ManualPaymentService:
    @staticmethod
    async def list_active_payment_methods(db: AsyncSession) -> List[AdminPaymentMethodResponse]:
        stmt = select(AdminPaymentMethod).where(AdminPaymentMethod.is_active == True).order_by(AdminPaymentMethod.display_order.asc(), AdminPaymentMethod.id.asc())
        res = await db.execute(stmt)
        methods = res.scalars().all()
        return [AdminPaymentMethodResponse.model_validate(m) for m in methods]

    @staticmethod
    async def list_all_payment_methods(db: AsyncSession) -> List[AdminPaymentMethodResponse]:
        stmt = select(AdminPaymentMethod).order_by(AdminPaymentMethod.display_order.asc(), AdminPaymentMethod.id.asc())
        res = await db.execute(stmt)
        methods = res.scalars().all()
        return [AdminPaymentMethodResponse.model_validate(m) for m in methods]

    @staticmethod
    async def create_payment_method(db: AsyncSession, req: AdminPaymentMethodRequest) -> AdminPaymentMethodResponse:
        pm = AdminPaymentMethod(
            method_type=req.methodType,
            title=req.title,
            bank_name=req.bankName,
            account_number=req.accountNumber,
            ifsc_code=req.ifscCode,
            account_holder_name=req.accountHolderName,
            upi_id=req.upiId,
            upi_qr_url=req.upiQrUrl,
            is_active=req.isActive,
            display_order=req.displayOrder,
        )
        db.add(pm)
        await db.commit()
        await db.refresh(pm)
        return AdminPaymentMethodResponse.model_validate(pm)

    @staticmethod
    async def update_payment_method(db: AsyncSession, method_id: int, req: AdminPaymentMethodRequest) -> AdminPaymentMethodResponse:
        stmt = select(AdminPaymentMethod).where(AdminPaymentMethod.id == method_id)
        res = await db.execute(stmt)
        pm = res.scalar_one_or_none()
        if not pm:
            raise ResourceNotFoundError(f"Payment method #{method_id} not found")

        pm.method_type = req.methodType
        pm.title = req.title
        pm.bank_name = req.bankName
        pm.account_number = req.accountNumber
        pm.ifsc_code = req.ifscCode
        pm.account_holder_name = req.accountHolderName
        pm.upi_id = req.upiId
        pm.upi_qr_url = req.upiQrUrl
        pm.is_active = req.isActive
        pm.display_order = req.displayOrder
        await db.commit()
        await db.refresh(pm)
        return AdminPaymentMethodResponse.model_validate(pm)

    @staticmethod
    async def toggle_payment_method_status(db: AsyncSession, method_id: int, is_active: bool) -> AdminPaymentMethodResponse:
        stmt = select(AdminPaymentMethod).where(AdminPaymentMethod.id == method_id)
        res = await db.execute(stmt)
        pm = res.scalar_one_or_none()
        if not pm:
            raise ResourceNotFoundError(f"Payment method #{method_id} not found")

        pm.is_active = is_active
        await db.commit()
        await db.refresh(pm)
        return AdminPaymentMethodResponse.model_validate(pm)

    @staticmethod
    async def delete_payment_method(db: AsyncSession, method_id: int) -> bool:
        stmt = select(AdminPaymentMethod).where(AdminPaymentMethod.id == method_id)
        res = await db.execute(stmt)
        pm = res.scalar_one_or_none()
        if not pm:
            raise ResourceNotFoundError(f"Payment method #{method_id} not found")

        await db.delete(pm)
        await db.commit()
        return True

    @staticmethod
    async def request_plan_activation(db: AsyncSession, user: User, req: PlanPurchaseRequest) -> PendingSubscriptionRequestResponse:
        # Check plan exists
        stmt_plan = select(Plan).where(Plan.id == req.planId)
        res_plan = await db.execute(stmt_plan)
        plan = res_plan.scalar_one_or_none()
        if not plan:
            raise ResourceNotFoundError(f"Plan #{req.planId} not found")

        # Check for existing pending request with same UTR
        stmt_dup = select(SubscriptionPayment).where(SubscriptionPayment.utr_number == req.utrNumber.strip())
        res_dup = await db.execute(stmt_dup)
        if res_dup.scalar_one_or_none():
            raise ValidationError(f"A payment verification request with UTR '{req.utrNumber}' has already been submitted.")

        # Compute amounts
        base_amt = plan.monthly_price
        gst_amt = (base_amt * plan.gst_percentage) / Decimal("100.00")
        tot_amt = base_amt + gst_amt

        now = datetime.now(timezone.utc)
        # Create or update subscription record
        stmt_sub = select(Subscription).where(Subscription.user_id == user.id).order_by(Subscription.id.desc())
        res_sub = await db.execute(stmt_sub)
        sub = res_sub.scalars().first()

        period_end = now + timedelta(days=30 if plan.subscription_type == "MONTHLY" else 90 if plan.subscription_type == "QUARTERLY" else 365)

        if not sub:
            sub = Subscription(
                user_id=user.id,
                plan_id=plan.id,
                status="PENDING_APPROVAL",
                start_at=now,
                current_period_start=now,
                current_period_end=period_end,
                auto_renew=True,
                payment_provider="MANUAL_UTR"
            )
            db.add(sub)
            await db.flush()
        else:
            sub.plan_id = plan.id
            sub.status = "PENDING_APPROVAL"
            sub.payment_provider = "MANUAL_UTR"
            db.add(sub)
            await db.flush()

        # Create SubscriptionPayment record
        payment = SubscriptionPayment(
            user_id=user.id,
            subscription_id=sub.id,
            plan_id=plan.id,
            amount=base_amt,
            gst_amount=gst_amt,
            total_amount=tot_amt,
            currency="INR",
            payment_provider="MANUAL_UTR",
            payment_mode=req.paymentMode,
            utr_number=req.utrNumber.strip(),
            user_remarks=req.userRemarks,
            status="PENDING_APPROVAL",
            created_at=now
        )
        db.add(payment)
        await db.commit()
        await db.refresh(payment)

        user_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email.split('@')[0]

        return PendingSubscriptionRequestResponse(
            paymentId=payment.id,
            subscriptionId=sub.id,
            userId=user.id,
            userEmail=user.email,
            userName=user_name,
            planId=plan.id,
            planCode=plan.code,
            planName=plan.name,
            amount=payment.amount,
            gstAmount=payment.gst_amount,
            totalAmount=payment.total_amount,
            paymentMode=payment.payment_mode,
            utrNumber=payment.utr_number,
            userRemarks=payment.user_remarks,
            adminNotes=payment.admin_notes,
            status=payment.status,
            requestedAt=payment.created_at
        )

    @staticmethod
    async def list_pending_subscription_requests(db: AsyncSession) -> List[PendingSubscriptionRequestResponse]:
        stmt = (
            select(SubscriptionPayment, User, Plan)
            .join(User, SubscriptionPayment.user_id == User.id)
            .join(Plan, SubscriptionPayment.plan_id == Plan.id)
            .where(SubscriptionPayment.status == "PENDING_APPROVAL")
            .order_by(SubscriptionPayment.id.desc())
        )
        res = await db.execute(stmt)
        rows = res.all()

        results = []
        for payment, user, plan in rows:
            user_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email.split('@')[0]
            results.append(PendingSubscriptionRequestResponse(
                paymentId=payment.id,
                subscriptionId=payment.subscription_id,
                userId=user.id,
                userEmail=user.email,
                userName=user_name,
                planId=plan.id,
                planCode=plan.code,
                planName=plan.name,
                amount=payment.amount,
                gstAmount=payment.gst_amount,
                totalAmount=payment.total_amount,
                paymentMode=payment.payment_mode,
                utrNumber=payment.utr_number,
                userRemarks=payment.user_remarks,
                adminNotes=payment.admin_notes,
                status=payment.status,
                requestedAt=payment.created_at
            ))
        return results

    @staticmethod
    async def approve_subscription_request(db: AsyncSession, payment_id: int, admin_user: User, admin_notes: Optional[str] = None) -> PendingSubscriptionRequestResponse:
        stmt = (
            select(SubscriptionPayment, User, Plan)
            .join(User, SubscriptionPayment.user_id == User.id)
            .join(Plan, SubscriptionPayment.plan_id == Plan.id)
            .where(SubscriptionPayment.id == payment_id)
        )
        res = await db.execute(stmt)
        row = res.first()
        if not row:
            raise ResourceNotFoundError(f"Payment request #{payment_id} not found")

        payment, user, plan = row
        now = datetime.now(timezone.utc)

        # 1. Update Payment
        payment.status = "SUCCESS"
        payment.paid_at = now
        payment.approved_by_id = admin_user.id
        payment.approved_at = now
        payment.admin_notes = admin_notes or "Verified against bank/UPI statement UTR"
        db.add(payment)

        # 2. Activate Subscription
        period_days = 30 if plan.subscription_type == "MONTHLY" else 90 if plan.subscription_type == "QUARTERLY" else 365
        stmt_sub = select(Subscription).where(Subscription.id == payment.subscription_id)
        res_sub = await db.execute(stmt_sub)
        sub = res_sub.scalar_one_or_none()

        if sub:
            sub.status = "ACTIVE"
            sub.start_at = now
            sub.current_period_start = now
            sub.current_period_end = now + timedelta(days=period_days)
            db.add(sub)

        # 3. Record in User Wallet Ledger
        stmt_uw = select(Wallet).where(Wallet.user_id == user.id)
        res_uw = await db.execute(stmt_uw)
        user_wallet = res_uw.scalar_one_or_none()
        if user_wallet:
            u_tx = WalletTransaction(
                wallet_id=user_wallet.id,
                amount=payment.total_amount,
                balance_before=user_wallet.balance,
                balance_after=user_wallet.balance,
                transaction_type="PLAN_PURCHASE",
                description=f"Plan subscription for {plan.name} (UTR: {payment.utr_number})",
                reference_type="SUBSCRIPTION_PAYMENT",
                reference_id=str(payment.id),
                status="COMPLETED",
                created_at=now
            )
            db.add(u_tx)

        # 4. Record in Admin Plan Wallet Ledger
        stmt_aw = select(Wallet).where(Wallet.user_id == admin_user.id)
        res_aw = await db.execute(stmt_aw)
        admin_wallet = res_aw.scalar_one_or_none()
        if admin_wallet:
            admin_wallet.balance += payment.total_amount
            admin_wallet.version += 1
            db.add(admin_wallet)
            a_tx = WalletTransaction(
                wallet_id=admin_wallet.id,
                amount=payment.total_amount,
                balance_before=admin_wallet.balance - payment.total_amount,
                balance_after=admin_wallet.balance,
                transaction_type="SUBSCRIPTION_REVENUE",
                description=f"Plan revenue from {user.email} for {plan.name} (UTR: {payment.utr_number})",
                reference_type="SUBSCRIPTION_PAYMENT",
                reference_id=str(payment.id),
                status="COMPLETED",
                created_at=now
            )
            db.add(a_tx)

        # 5. Log Subscription Event
        event = SubscriptionEvent(
            subscription_id=sub.id if sub else payment.subscription_id,
            event_type="ACTIVATED_MANUAL_UTR",
            new_plan_id=plan.id,
            new_status="ACTIVE",
            reference_id=payment.utr_number,
            created_at=now
        )
        db.add(event)

        await db.commit()
        await db.refresh(payment)

        user_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email.split('@')[0]

        return PendingSubscriptionRequestResponse(
            paymentId=payment.id,
            subscriptionId=payment.subscription_id,
            userId=user.id,
            userEmail=user.email,
            userName=user_name,
            planId=plan.id,
            planCode=plan.code,
            planName=plan.name,
            amount=payment.amount,
            gstAmount=payment.gst_amount,
            totalAmount=payment.total_amount,
            paymentMode=payment.payment_mode,
            utrNumber=payment.utr_number,
            userRemarks=payment.user_remarks,
            adminNotes=payment.admin_notes,
            status=payment.status,
            requestedAt=payment.created_at
        )

    @staticmethod
    async def reject_subscription_request(db: AsyncSession, payment_id: int, admin_user: User, admin_notes: Optional[str] = None) -> PendingSubscriptionRequestResponse:
        stmt = (
            select(SubscriptionPayment, User, Plan)
            .join(User, SubscriptionPayment.user_id == User.id)
            .join(Plan, SubscriptionPayment.plan_id == Plan.id)
            .where(SubscriptionPayment.id == payment_id)
        )
        res = await db.execute(stmt)
        row = res.first()
        if not row:
            raise ResourceNotFoundError(f"Payment request #{payment_id} not found")

        payment, user, plan = row
        payment.status = "REJECTED"
        payment.admin_notes = admin_notes or "UTR verification failed. Please check with your bank."
        payment.approved_by_id = admin_user.id
        payment.approved_at = datetime.now(timezone.utc)
        db.add(payment)

        if payment.subscription_id:
            stmt_sub = select(Subscription).where(Subscription.id == payment.subscription_id)
            res_sub = await db.execute(stmt_sub)
            sub = res_sub.scalar_one_or_none()
            if sub and sub.status == "PENDING_APPROVAL":
                sub.status = "REJECTED"
                db.add(sub)

        await db.commit()
        await db.refresh(payment)

        user_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email.split('@')[0]

        return PendingSubscriptionRequestResponse(
            paymentId=payment.id,
            subscriptionId=payment.subscription_id,
            userId=user.id,
            userEmail=user.email,
            userName=user_name,
            planId=plan.id,
            planCode=plan.code,
            planName=plan.name,
            amount=payment.amount,
            gstAmount=payment.gst_amount,
            totalAmount=payment.total_amount,
            paymentMode=payment.payment_mode,
            utrNumber=payment.utr_number,
            userRemarks=payment.user_remarks,
            adminNotes=payment.admin_notes,
            status=payment.status,
            requestedAt=payment.created_at
        )

    @staticmethod
    async def get_admin_plan_wallet_ledger(db: AsyncSession) -> AdminPlanWalletLedgerResponse:
        # Total Approved Revenue
        stmt_rev = select(func.coalesce(func.sum(SubscriptionPayment.total_amount), Decimal("0.00"))).where(SubscriptionPayment.status == "SUCCESS")
        res_rev = await db.execute(stmt_rev)
        total_rev = res_rev.scalar() or Decimal("0.00")

        # Pending Revenue
        stmt_pend = select(func.coalesce(func.sum(SubscriptionPayment.total_amount), Decimal("0.00"))).where(SubscriptionPayment.status == "PENDING_APPROVAL")
        res_pend = await db.execute(stmt_pend)
        pending_rev = res_pend.scalar() or Decimal("0.00")

        # Active Subscribers
        stmt_active = select(func.count(Subscription.id)).where(Subscription.status == "ACTIVE")
        res_active = await db.execute(stmt_active)
        active_subscribers = res_active.scalar() or 0

        # Ledger of approved transactions
        stmt_ledger = (
            select(SubscriptionPayment, User, Plan)
            .join(User, SubscriptionPayment.user_id == User.id)
            .join(Plan, SubscriptionPayment.plan_id == Plan.id)
            .where(SubscriptionPayment.status == "SUCCESS")
            .order_by(SubscriptionPayment.id.desc())
            .limit(50)
        )
        res_ledger = await db.execute(stmt_ledger)
        rows = res_ledger.all()

        ledger_items = []
        for payment, user, plan in rows:
            user_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email.split('@')[0]
            approved_by_str = "Super Admin" if payment.approved_by_id else "System"
            ledger_items.append(PlanWalletLedgerItem(
                id=payment.id,
                paymentId=payment.id,
                userId=user.id,
                userEmail=user.email,
                userName=user_name,
                planName=plan.name,
                amount=payment.total_amount,
                utrNumber=payment.utr_number or "N/A",
                approvedBy=approved_by_str,
                approvedAt=payment.approved_at or payment.created_at
            ))

        return AdminPlanWalletLedgerResponse(
            totalRevenue=total_rev,
            pendingRevenue=pending_rev,
            activeSubscribersCount=active_subscribers,
            totalTransactionsCount=len(ledger_items),
            ledger=ledger_items
        )
