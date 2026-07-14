"""Billing API routes: plans, checkout, Razorpay create/verify, payment history."""

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.modules.auth.model import User
from app.modules.billing import service
from app.modules.billing.schema import (
    BillingPlansSuccessResponse,
    CheckoutRequest,
    CheckoutSuccessResponse,
    CreateOrderRequest,
    CreateOrderSuccessResponse,
    CreateSubscriptionRequest,
    CreateSubscriptionSuccessResponse,
    AutoRenewRequest,
    AutoRenewSuccessResponse,
    CancelSubscriptionRequest,
    CancelSubscriptionSuccessResponse,
    CurrentPlanSuccessResponse,
    InvoicesSuccessResponse,
    InvoiceDetailSuccessResponse,
    ResendInvoiceRequest,
    ResendInvoiceSuccessResponse,
    PaymentDetailSuccessResponse,
    PaymentHistorySuccessResponse,
    PlanComparisonSuccessResponse,
    RetryPaymentRequest,
    RetryPaymentSuccessResponse,
    SubscriptionHistorySuccessResponse,
    SubscriptionStatusSuccessResponse,
    VerifyPaymentRequest,
    VerifyPaymentSuccessResponse,
)

router = APIRouter(
    prefix="/v1/billing",
    tags=["Billing"],
)


def _billing_error_response(exc: Exception) -> JSONResponse | None:
    if isinstance(exc, service.BillingUserNotFoundError):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": exc.message},
        )
    if isinstance(exc, service.BillingAccessDeniedError):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"success": False, "message": exc.message},
        )
    if isinstance(exc, service.BillingValidationError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": exc.message},
        )
    return None


@router.get(
    "/plans",
    status_code=status.HTTP_200_OK,
    response_model=BillingPlansSuccessResponse,
    summary="List active subscription plans",
)
def list_billing_plans(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all active plans with prices, features, and current/recommended flags."""
    return service.get_plans(db, current_user)


@router.post(
    "/checkout",
    status_code=status.HTTP_200_OK,
    response_model=CheckoutSuccessResponse,
    summary="Prepare checkout preview",
)
def prepare_billing_checkout(
    payload: CheckoutRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Validate plan selection and return GST-aware checkout totals."""
    try:
        return service.prepare_checkout(db, current_user, payload)
    except Exception as exc:
        error = _billing_error_response(exc)
        if error is not None:
            return error
        raise


@router.post(
    "/create-order",
    status_code=status.HTTP_200_OK,
    response_model=CreateOrderSuccessResponse,
    summary="Create Razorpay one-time payment order",
)
def create_billing_order(
    payload: CreateOrderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create Razorpay order and store a pending payment_transaction."""
    try:
        return service.create_order(db, current_user, payload)
    except Exception as exc:
        error = _billing_error_response(exc)
        if error is not None:
            return error
        raise


@router.post(
    "/create-subscription",
    status_code=status.HTTP_200_OK,
    response_model=CreateSubscriptionSuccessResponse,
    summary="Create Razorpay AutoPay subscription",
)
def create_billing_subscription(
    payload: CreateSubscriptionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create Razorpay subscription for optional Auto Renew checkout."""
    try:
        return service.create_subscription_order(db, current_user, payload)
    except Exception as exc:
        error = _billing_error_response(exc)
        if error is not None:
            return error
        raise


@router.post(
    "/verify-payment",
    status_code=status.HTTP_200_OK,
    response_model=VerifyPaymentSuccessResponse,
    summary="Verify Razorpay payment and activate plan",
)
def verify_billing_payment(
    payload: VerifyPaymentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Verify Razorpay signature (order or subscription), mark payment success,
    activate user_plan, write subscription_history, and reset chatbot_usage.
    """
    try:
        return service.verify_payment(db, current_user, payload)
    except Exception as exc:
        error = _billing_error_response(exc)
        if error is not None:
            return error
        raise


@router.post(
    "/disable-auto-renew",
    status_code=status.HTTP_200_OK,
    response_model=AutoRenewSuccessResponse,
    summary="Disable AutoPay at cycle end",
)
def disable_billing_auto_renew(
    payload: AutoRenewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cancel future renewals; keep the current period active until expiry."""
    try:
        return service.disable_user_auto_renew(db, current_user, payload)
    except Exception as exc:
        error = _billing_error_response(exc)
        if error is not None:
            return error
        raise


@router.post(
    "/enable-auto-renew",
    status_code=status.HTTP_200_OK,
    response_model=AutoRenewSuccessResponse,
    summary="Enable AutoPay again",
)
def enable_billing_auto_renew(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Resume subscription or create a new one (may require Checkout)."""
    try:
        return service.enable_user_auto_renew(db, current_user)
    except Exception as exc:
        error = _billing_error_response(exc)
        if error is not None:
            return error
        raise


@router.post(
    "/cancel-subscription",
    status_code=status.HTTP_200_OK,
    response_model=CancelSubscriptionSuccessResponse,
    summary="Cancel Auto Renew at cycle end",
)
def cancel_billing_subscription(
    payload: CancelSubscriptionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Disable future Auto Renew. Current plan stays active until subscription_end.
    Does NOT immediately downgrade to Free.
    """
    try:
        return service.cancel_user_subscription(db, current_user, payload)
    except Exception as exc:
        error = _billing_error_response(exc)
        if error is not None:
            return error
        raise


@router.post(
    "/retry-payment",
    status_code=status.HTTP_200_OK,
    response_model=RetryPaymentSuccessResponse,
    summary="Retry a failed payment",
)
def retry_billing_payment(
    payload: RetryPaymentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new Razorpay order for a failed payment_transaction."""
    try:
        return service.retry_user_payment(db, current_user, payload)
    except Exception as exc:
        error = _billing_error_response(exc)
        if error is not None:
            return error
        raise


@router.get(
    "/subscription-status",
    status_code=status.HTTP_200_OK,
    response_model=SubscriptionStatusSuccessResponse,
    summary="Get subscription status snapshot",
)
def get_billing_subscription_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return plan status, Auto Renew, remaining days, can_cancel / can_retry flags."""
    try:
        return service.get_subscription_status(db, current_user)
    except Exception as exc:
        error = _billing_error_response(exc)
        if error is not None:
            return error
        raise


@router.get(
    "/plan-comparison",
    status_code=status.HTTP_200_OK,
    response_model=PlanComparisonSuccessResponse,
    summary="Get plan comparison matrix",
)
def get_billing_plan_comparison(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return feature rows for Free / Starter / Pro / Enterprise comparison."""
    return service.get_plan_comparison(db, current_user)


@router.get(
    "/current-plan",
    status_code=status.HTTP_200_OK,
    response_model=CurrentPlanSuccessResponse,
    summary="Get current subscription plan",
)
def get_current_billing_plan(
    user_id: int | None = Query(
        default=None,
        description=(
            "Optional target user id. Users may only request their own plan. "
            "Admin may request User-role accounts. SuperAdmin may request any user."
        ),
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the logged-in user's (or permitted target's) current subscription."""
    try:
        return service.get_current_plan(db, current_user, user_id=user_id)
    except Exception as exc:
        error = _billing_error_response(exc)
        if error is not None:
            return error
        raise


@router.get(
    "/payment-history",
    status_code=status.HTTP_200_OK,
    response_model=PaymentHistorySuccessResponse,
    summary="Get payment history",
)
def get_billing_payment_history(
    user_id: int | None = Query(
        default=None,
        description="Optional target user id for Admin/SuperAdmin viewers.",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return payment history newest first."""
    try:
        return service.get_payment_history(db, current_user, user_id=user_id)
    except Exception as exc:
        error = _billing_error_response(exc)
        if error is not None:
            return error
        raise


@router.get(
    "/payment/{payment_id}",
    status_code=status.HTTP_200_OK,
    response_model=PaymentDetailSuccessResponse,
    summary="Get payment details by id",
)
def get_billing_payment_detail(
    payment_id: int,
    user_id: int | None = Query(
        default=None,
        description="Optional target user id for Admin/SuperAdmin viewers.",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return a single payment_transaction the actor may view."""
    try:
        return service.get_payment_detail(
            db,
            current_user,
            payment_id,
            user_id=user_id,
        )
    except Exception as exc:
        error = _billing_error_response(exc)
        if error is not None:
            return error
        raise


@router.get(
    "/subscription-history",
    status_code=status.HTTP_200_OK,
    response_model=SubscriptionHistorySuccessResponse,
    summary="Get subscription change history",
)
def get_billing_subscription_history(
    user_id: int | None = Query(
        default=None,
        description="Optional target user id for Admin/SuperAdmin viewers.",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return purchase / upgrade / downgrade / renew / cancel / expire history."""
    try:
        return service.get_subscription_history(db, current_user, user_id=user_id)
    except Exception as exc:
        error = _billing_error_response(exc)
        if error is not None:
            return error
        raise


@router.get(
    "/invoices",
    status_code=status.HTTP_200_OK,
    response_model=InvoicesSuccessResponse,
    summary="Get invoices",
)
def get_billing_invoices(
    user_id: int | None = Query(
        default=None,
        description="Optional target user id for Admin/SuperAdmin viewers.",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return invoices newest first."""
    try:
        return service.get_invoices(db, current_user, user_id=user_id)
    except Exception as exc:
        error = _billing_error_response(exc)
        if error is not None:
            return error
        raise


@router.get(
    "/invoice/{invoice_id}",
    status_code=status.HTTP_200_OK,
    response_model=InvoiceDetailSuccessResponse,
    summary="Get invoice details",
)
def get_billing_invoice_detail(
    invoice_id: int,
    user_id: int | None = Query(
        default=None,
        description="Optional target user id for Admin/SuperAdmin viewers.",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return a single invoice the actor is allowed to view."""
    try:
        return service.get_invoice_detail(
            db,
            current_user,
            invoice_id,
            user_id=user_id,
        )
    except Exception as exc:
        error = _billing_error_response(exc)
        if error is not None:
            return error
        raise


@router.get(
    "/invoice/{invoice_id}/download",
    status_code=status.HTTP_200_OK,
    summary="Download invoice PDF",
)
def download_billing_invoice(
    invoice_id: int,
    user_id: int | None = Query(
        default=None,
        description="Optional target user id for Admin/SuperAdmin viewers.",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download the invoice PDF file (owner / Admin / SuperAdmin)."""
    try:
        path, invoice = service.resolve_invoice_pdf_path(
            db,
            current_user,
            invoice_id,
            user_id=user_id,
        )
        filename = f"{invoice.invoice_number}.pdf"
        return FileResponse(
            path=str(path),
            media_type="application/pdf",
            filename=filename,
        )
    except Exception as exc:
        error = _billing_error_response(exc)
        if error is not None:
            return error
        raise


@router.post(
    "/resend-invoice",
    status_code=status.HTTP_200_OK,
    response_model=ResendInvoiceSuccessResponse,
    summary="Resend invoice email",
)
def resend_billing_invoice(
    payload: ResendInvoiceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Resend the invoice PDF to the customer billing email."""
    try:
        return service.resend_invoice_email(db, current_user, payload)
    except Exception as exc:
        error = _billing_error_response(exc)
        if error is not None:
            return error
        raise
