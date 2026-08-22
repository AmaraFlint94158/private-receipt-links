from private_receipts.order_workflow import OrderWorkflow


class ReceiptStorage:
    def __init__(self, found: bool) -> None:
        self.found = found
        self.download_calls = 0

    def head_object(self, bucket: str, key: str) -> dict:
        return {"found": self.found}

    def presign_download(self, bucket: str, key: str, order_id: str) -> dict:
        self.download_calls += 1
        return {"url": "https://download.example/signed-receipt"}


def test_customer_only_gets_link_after_receipt_arrives() -> None:
    pending_storage = ReceiptStorage(found=False)
    pending = OrderWorkflow(pending_storage, "receipts").customer_update("order_1042")
    assert pending.status == "awaiting_fulfillment"
    assert pending.receipt_download_url is None
    assert pending_storage.download_calls == 0

    ready_storage = ReceiptStorage(found=True)
    ready = OrderWorkflow(ready_storage, "receipts").customer_update("order_1042")
    assert ready.status == "fulfilled"
    assert ready.receipt_download_url == "https://download.example/signed-receipt"
    assert ready.expires_seconds == 300
    assert ready_storage.download_calls == 1
