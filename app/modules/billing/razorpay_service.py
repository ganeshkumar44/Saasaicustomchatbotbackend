"""Reusable Razorpay client for one-time orders and AutoPay subscriptions."""

from __future__ import annotations

import logging
from typing import Any

import razorpay
from razorpay.errors import BadRequestError, GatewayError, ServerError

from app.core import messages
from app.core.config import get_settings
from app.modules.billing.checkout import BillingValidationError

logger = logging.getLogger(__name__)


class RazorpayServiceError(BillingValidationError):
    """Raised when Razorpay SDK / API calls fail."""


class RazorpayService:
    """Thin wrapper around the Razorpay Python SDK."""

    def __init__(
        self,
        *,
        key_id: str | None = None,
        key_secret: str | None = None,
    ) -> None:
        settings = get_settings()
        self.key_id = (key_id if key_id is not None else settings.RAZORPAY_KEY_ID).strip()
        self.key_secret = (
            key_secret if key_secret is not None else settings.RAZORPAY_KEY_SECRET
        ).strip()
        self.currency = (settings.RAZORPAY_CURRENCY or "INR").upper()
        self.environment = settings.RAZORPAY_ENVIRONMENT

        if not self.key_id or not self.key_secret:
            raise RazorpayServiceError(messages.BILLING_RAZORPAY_NOT_CONFIGURED)

        self._client = razorpay.Client(auth=(self.key_id, self.key_secret))

    def create_order(
        self,
        *,
        amount_paise: int,
        currency: str | None = None,
        receipt: str | None = None,
        notes: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Create a Razorpay one-time order (amount in paise)."""
        if amount_paise <= 0:
            raise RazorpayServiceError(messages.BILLING_ORDER_AMOUNT_INVALID)

        payload: dict[str, Any] = {
            "amount": amount_paise,
            "currency": (currency or self.currency).upper(),
            "payment_capture": 1,
        }
        if receipt:
            payload["receipt"] = receipt[:40]
        if notes:
            payload["notes"] = notes

        try:
            order = self._client.order.create(data=payload)
        except (BadRequestError, GatewayError, ServerError) as exc:
            logger.exception("Razorpay order.create failed: %s", exc)
            raise RazorpayServiceError(messages.BILLING_RAZORPAY_ORDER_FAILED) from exc
        except Exception as exc:
            logger.exception("Razorpay network/SDK error during order.create")
            raise RazorpayServiceError(messages.BILLING_RAZORPAY_NETWORK_ERROR) from exc

        if not isinstance(order, dict) or not order.get("id"):
            raise RazorpayServiceError(messages.BILLING_RAZORPAY_ORDER_FAILED)
        return order

    def fetch_order(self, order_id: str) -> dict[str, Any]:
        """Fetch an existing Razorpay order by id."""
        try:
            order = self._client.order.fetch(order_id)
        except (BadRequestError, GatewayError, ServerError) as exc:
            logger.exception("Razorpay order.fetch failed order_id=%s", order_id)
            raise RazorpayServiceError(messages.BILLING_RAZORPAY_ORDER_FAILED) from exc
        except Exception as exc:
            logger.exception("Razorpay network/SDK error during order.fetch")
            raise RazorpayServiceError(messages.BILLING_RAZORPAY_NETWORK_ERROR) from exc

        if not isinstance(order, dict):
            raise RazorpayServiceError(messages.BILLING_RAZORPAY_ORDER_FAILED)
        return order

    def fetch_payment(self, payment_id: str) -> dict[str, Any] | None:
        """Fetch a Razorpay payment by id. Returns None when unavailable."""
        try:
            payment = self._client.payment.fetch(payment_id)
        except (BadRequestError, GatewayError, ServerError):
            logger.warning("Razorpay payment.fetch failed payment_id=%s", payment_id)
            return None
        except Exception:
            logger.warning(
                "Razorpay network/SDK error during payment.fetch payment_id=%s",
                payment_id,
                exc_info=True,
            )
            return None
        return payment if isinstance(payment, dict) else None

    def verify_payment_signature(
        self,
        *,
        razorpay_order_id: str,
        razorpay_payment_id: str,
        razorpay_signature: str,
    ) -> None:
        """Verify one-time checkout signature."""
        payload = {
            "razorpay_order_id": razorpay_order_id,
            "razorpay_payment_id": razorpay_payment_id,
            "razorpay_signature": razorpay_signature,
        }
        try:
            self._client.utility.verify_payment_signature(payload)
        except Exception as exc:
            logger.warning(
                "Razorpay order signature verification failed order_id=%s",
                razorpay_order_id,
            )
            raise RazorpayServiceError(
                messages.BILLING_PAYMENT_VERIFICATION_FAILED
            ) from exc

    def verify_subscription_payment_signature(
        self,
        *,
        razorpay_subscription_id: str,
        razorpay_payment_id: str,
        razorpay_signature: str,
    ) -> None:
        """Verify subscription checkout signature."""
        payload = {
            "razorpay_subscription_id": razorpay_subscription_id,
            "razorpay_payment_id": razorpay_payment_id,
            "razorpay_signature": razorpay_signature,
        }
        try:
            self._client.utility.verify_subscription_payment_signature(payload)
        except Exception as exc:
            logger.warning(
                "Razorpay subscription signature verification failed sub_id=%s",
                razorpay_subscription_id,
            )
            raise RazorpayServiceError(
                messages.BILLING_PAYMENT_VERIFICATION_FAILED
            ) from exc

    def create_customer(
        self,
        *,
        name: str,
        email: str,
        contact: str | None = None,
        notes: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Create or reuse a Razorpay customer (fail_existing=0)."""
        payload: dict[str, Any] = {
            "name": name[:50] or "Customer",
            "email": email,
            "fail_existing": "0",
        }
        if contact:
            payload["contact"] = contact
        if notes:
            payload["notes"] = notes
        try:
            customer = self._client.customer.create(data=payload)
        except (BadRequestError, GatewayError, ServerError) as exc:
            logger.exception("Razorpay customer.create failed: %s", exc)
            raise RazorpayServiceError(messages.BILLING_RAZORPAY_CUSTOMER_FAILED) from exc
        except Exception as exc:
            logger.exception("Razorpay network/SDK error during customer.create")
            raise RazorpayServiceError(messages.BILLING_RAZORPAY_NETWORK_ERROR) from exc

        if not isinstance(customer, dict) or not customer.get("id"):
            raise RazorpayServiceError(messages.BILLING_RAZORPAY_CUSTOMER_FAILED)
        return customer

    def create_plan(
        self,
        *,
        period: str,
        interval: int,
        amount_paise: int,
        currency: str | None = None,
        name: str,
        description: str | None = None,
    ) -> dict[str, Any]:
        """Create a Razorpay billing plan used by subscriptions."""
        if amount_paise <= 0:
            raise RazorpayServiceError(messages.BILLING_ORDER_AMOUNT_INVALID)
        payload: dict[str, Any] = {
            "period": period,
            "interval": interval,
            "item": {
                "name": name[:255],
                "amount": amount_paise,
                "currency": (currency or self.currency).upper(),
            },
        }
        if description:
            payload["item"]["description"] = description[:255]
        try:
            plan = self._client.plan.create(data=payload)
        except (BadRequestError, GatewayError, ServerError) as exc:
            logger.exception("Razorpay plan.create failed: %s", exc)
            raise RazorpayServiceError(messages.BILLING_RAZORPAY_PLAN_FAILED) from exc
        except Exception as exc:
            logger.exception("Razorpay network/SDK error during plan.create")
            raise RazorpayServiceError(messages.BILLING_RAZORPAY_NETWORK_ERROR) from exc

        if not isinstance(plan, dict) or not plan.get("id"):
            raise RazorpayServiceError(messages.BILLING_RAZORPAY_PLAN_FAILED)
        return plan

    def create_subscription(
        self,
        *,
        plan_id: str,
        total_count: int,
        customer_id: str | None = None,
        notes: dict[str, str] | None = None,
        customer_notify: int = 1,
    ) -> dict[str, Any]:
        """Create a Razorpay subscription for AutoPay."""
        payload: dict[str, Any] = {
            "plan_id": plan_id,
            "total_count": max(int(total_count), 1),
            "quantity": 1,
            "customer_notify": customer_notify,
        }
        if customer_id:
            payload["customer_id"] = customer_id
        if notes:
            payload["notes"] = notes
        try:
            subscription = self._client.subscription.create(data=payload)
        except (BadRequestError, GatewayError, ServerError) as exc:
            logger.exception("Razorpay subscription.create failed: %s", exc)
            raise RazorpayServiceError(
                messages.BILLING_RAZORPAY_SUBSCRIPTION_FAILED
            ) from exc
        except Exception as exc:
            logger.exception("Razorpay network/SDK error during subscription.create")
            raise RazorpayServiceError(messages.BILLING_RAZORPAY_NETWORK_ERROR) from exc

        if not isinstance(subscription, dict) or not subscription.get("id"):
            raise RazorpayServiceError(messages.BILLING_RAZORPAY_SUBSCRIPTION_FAILED)
        return subscription

    def fetch_subscription(self, subscription_id: str) -> dict[str, Any]:
        """Fetch a Razorpay subscription by id."""
        try:
            subscription = self._client.subscription.fetch(subscription_id)
        except (BadRequestError, GatewayError, ServerError) as exc:
            logger.exception(
                "Razorpay subscription.fetch failed sub_id=%s", subscription_id
            )
            raise RazorpayServiceError(messages.BILLING_SUBSCRIPTION_INVALID) from exc
        except Exception as exc:
            logger.exception("Razorpay network/SDK error during subscription.fetch")
            raise RazorpayServiceError(messages.BILLING_RAZORPAY_NETWORK_ERROR) from exc

        if not isinstance(subscription, dict):
            raise RazorpayServiceError(messages.BILLING_SUBSCRIPTION_INVALID)
        return subscription

    def cancel_subscription(
        self,
        subscription_id: str,
        *,
        cancel_at_cycle_end: bool = True,
    ) -> dict[str, Any]:
        """Cancel a subscription (default: at end of current cycle)."""
        try:
            result = self._client.subscription.cancel(
                subscription_id,
                {"cancel_at_cycle_end": 1 if cancel_at_cycle_end else 0},
            )
        except (BadRequestError, GatewayError, ServerError) as exc:
            logger.exception(
                "Razorpay subscription.cancel failed sub_id=%s", subscription_id
            )
            raise RazorpayServiceError(messages.BILLING_SUBSCRIPTION_INVALID) from exc
        except Exception as exc:
            logger.exception("Razorpay network/SDK error during subscription.cancel")
            raise RazorpayServiceError(messages.BILLING_RAZORPAY_NETWORK_ERROR) from exc

        return result if isinstance(result, dict) else {"id": subscription_id}

    def resume_subscription(self, subscription_id: str) -> dict[str, Any] | None:
        """
        Resume a halted subscription when Razorpay allows it.

        Returns None when resume is not supported for the current status.
        """
        try:
            result = self._client.subscription.resume(
                subscription_id,
                {"resume_at": "now"},
            )
        except Exception:
            logger.info(
                "Razorpay subscription.resume unavailable for sub_id=%s",
                subscription_id,
                exc_info=True,
            )
            return None
        return result if isinstance(result, dict) else None


def get_razorpay_service() -> RazorpayService:
    """Factory for a configured RazorpayService instance."""
    return RazorpayService()
