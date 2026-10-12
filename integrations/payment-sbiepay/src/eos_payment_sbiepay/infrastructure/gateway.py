"""The gateway port and its implementations.

`MockGateway` stands in for SBIePay in development and tests (PAYMENT_SBIEPAY_MODE=mock, refused unless
EOS_DEV_MODE=true). `SbiepayGateway` is the real gateway; its request and response fields, encryption,
double verification, refund and settlement formats come from the SBIePay merchant integration kit, which
has not been received yet, so every call raises GatewayUnavailableError until it is implemented."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Protocol

from .config import Config


class GatewayUnavailableError(Exception):
    pass


class GatewayResponseInvalidError(Exception):
    pass


@dataclass(frozen=True)
class RedirectForm:
    """An HTML form the payer's browser posts to the gateway."""

    action_url: str
    fields: dict[str, str]


@dataclass(frozen=True)
class VerifyResult:
    """Outcome of double verification: the gateway's own answer for one merchant order number."""

    status: str  # succeeded | failed | pending | not_found
    gateway_transaction_id: str | None = None
    payment_mode: str | None = None
    amount: Decimal | None = None
    failure_reason: str | None = None


@dataclass(frozen=True)
class RefundResult:
    status: str  # succeeded | failed | requested
    gateway_refund_id: str | None = None
    failure_reason: str | None = None


@dataclass(frozen=True)
class SettlementRow:
    reference: str | None
    gateway_transaction_id: str | None
    amount: Decimal
    status: str = "succeeded"


@dataclass(frozen=True)
class PaymentOrder:
    """What the gateway needs to know about a payment; never carries secrets."""

    reference: str
    merchant_id: str
    amount: Decimal
    currency: str
    description: str = ""
    payer: dict = field(default_factory=dict)


class Gateway(Protocol):
    def redirect_form(self, order: PaymentOrder, callback_url: str) -> RedirectForm: ...

    def parse_response(self, form: dict[str, str]) -> str:
        """Decrypt the browser-posted response and return the merchant order number (our reference).
        The response itself is never trusted; the caller confirms it with verify()."""
        ...

    def verify(self, order: PaymentOrder) -> VerifyResult: ...

    def refund(self, order: PaymentOrder, refund_id: str, amount: Decimal) -> RefundResult: ...

    def settlement(self, merchant_id: str, settlement_date: date) -> list[SettlementRow]: ...


class MockGateway:
    """In-memory gateway. The redirect form posts straight back to the callback with the outcome the
    payer picks (`mock_outcome`); verify() answers from what the mock recorded, like double verification."""

    transactions: dict[str, VerifyResult] = {}
    settlements: dict[tuple[str, date], list[SettlementRow]] = {}
    refunds: list[tuple[str, str, Decimal]] = []
    fail_refunds: bool = False

    @classmethod
    def reset(cls) -> None:
        cls.transactions, cls.settlements, cls.refunds, cls.fail_refunds = {}, {}, [], False

    def redirect_form(self, order: PaymentOrder, callback_url: str) -> RedirectForm:
        return RedirectForm(
            action_url=callback_url, fields={"mock_reference": order.reference, "mock_outcome": "success"}
        )

    def parse_response(self, form: dict[str, str]) -> str:
        reference = form.get("mock_reference", "")
        outcome = form.get("mock_outcome", "")
        if not reference or outcome not in ("success", "failure", "cancel"):
            raise GatewayResponseInvalidError("unrecognised mock gateway response")
        if reference not in self.transactions:
            if outcome == "success":
                self.transactions[reference] = VerifyResult(
                    "succeeded", gateway_transaction_id=f"MOCK{len(self.transactions) + 1:08d}", payment_mode="mock"
                )
            else:
                reason = "cancelled by payer" if outcome == "cancel" else "declined by mock gateway"
                self.transactions[reference] = VerifyResult("failed", failure_reason=reason)
        return reference

    def verify(self, order: PaymentOrder) -> VerifyResult:
        result = self.transactions.get(order.reference)
        if result is None:
            return VerifyResult("not_found")
        if result.status == "succeeded" and result.amount is None:
            return VerifyResult(
                "succeeded", result.gateway_transaction_id, result.payment_mode, order.amount, result.failure_reason
            )
        return result

    def refund(self, order: PaymentOrder, refund_id: str, amount: Decimal) -> RefundResult:
        if self.fail_refunds:
            return RefundResult("failed", failure_reason="refused by mock gateway")
        self.refunds.append((order.reference, refund_id, amount))
        return RefundResult("succeeded", gateway_refund_id=f"MOCKREF{len(self.refunds):06d}")

    def settlement(self, merchant_id: str, settlement_date: date) -> list[SettlementRow]:
        return list(self.settlements.get((merchant_id, settlement_date), []))


class SbiepayGateway:
    def __init__(self, config: Config):
        self.config = config

    def _unavailable(self):
        raise GatewayUnavailableError(
            "SBIePay gateway is not implemented yet: it needs the SBIePay merchant integration kit and an approved AES library"
        )

    def redirect_form(self, order: PaymentOrder, callback_url: str) -> RedirectForm:
        self._unavailable()
        raise AssertionError  # unreachable

    def parse_response(self, form: dict[str, str]) -> str:
        self._unavailable()
        raise AssertionError

    def verify(self, order: PaymentOrder) -> VerifyResult:
        self._unavailable()
        raise AssertionError

    def refund(self, order: PaymentOrder, refund_id: str, amount: Decimal) -> RefundResult:
        self._unavailable()
        raise AssertionError

    def settlement(self, merchant_id: str, settlement_date: date) -> list[SettlementRow]:
        self._unavailable()
        raise AssertionError


def gateway_for(config: Config) -> Gateway:
    return MockGateway() if config.mode == "mock" else SbiepayGateway(config)
