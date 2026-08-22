from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Protocol


class StoragePort(Protocol):
    def presign_upload(self, bucket: str, key: str, order_id: str) -> dict:
        """Return a signed upload description."""

    def head_object(self, bucket: str, key: str) -> dict:
        """Return object metadata including its found state."""

    def presign_download(self, bucket: str, key: str, order_id: str) -> dict:
        """Return a signed download description."""


class SerializableModel:
    def model_dump(self) -> dict:
        return asdict(self)


@dataclass
class CheckoutRequest(SerializableModel):
    order_id: str
    customer_email: str
    total_cents: int

    def __post_init__(self) -> None:
        if re.fullmatch(r"[A-Za-z0-9_-]{3,64}", self.order_id) is None:
            raise ValueError("order_id must be 3-64 letters, numbers, underscores, or hyphens")
        if not 3 <= len(self.customer_email) <= 254:
            raise ValueError("customer_email must be 3-254 characters")
        if self.total_cents <= 0:
            raise ValueError("total_cents must be greater than zero")


@dataclass
class CheckoutResult(SerializableModel):
    order_id: str
    status: str
    fulfillment_upload_url: str
    receipt_key: str


@dataclass
class CustomerOrderUpdate(SerializableModel):
    order_id: str
    status: str
    receipt_download_url: str | None = None
    expires_seconds: int | None = None


@dataclass
class OrderWorkflow:
    storage: StoragePort
    bucket: str

    @staticmethod
    def receipt_key(order_id: str) -> str:
        return f"receipts/{order_id}.pdf"

    def checkout(self, request: CheckoutRequest) -> CheckoutResult:
        key = self.receipt_key(request.order_id)
        signed = self.storage.presign_upload(self.bucket, key, request.order_id)
        return CheckoutResult(
            order_id=request.order_id,
            status="awaiting_fulfillment",
            fulfillment_upload_url=signed["url"],
            receipt_key=key,
        )

    def customer_update(self, order_id: str) -> CustomerOrderUpdate:
        key = self.receipt_key(order_id)
        receipt = self.storage.head_object(self.bucket, key)
        if not receipt.get("found"):
            return CustomerOrderUpdate(order_id=order_id, status="awaiting_fulfillment")

        signed = self.storage.presign_download(self.bucket, key, order_id)
        return CustomerOrderUpdate(
            order_id=order_id,
            status="fulfilled",
            receipt_download_url=signed["url"],
            expires_seconds=300,
        )
