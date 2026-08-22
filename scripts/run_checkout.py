from __future__ import annotations

import json

from private_receipts.infrai_client import InfraiStorage
from private_receipts.order_workflow import CheckoutRequest, OrderWorkflow


def main() -> None:
    storage = InfraiStorage()
    try:
        bucket = "shop-private-receipts"
        workflow = OrderWorkflow(storage=storage, bucket=bucket)
        result = workflow.checkout(
            CheckoutRequest(order_id="order_1042", customer_email="buyer@example.com", total_cents=4900)
        )
        print(json.dumps(result.model_dump(), indent=2))
    finally:
        storage.client.close()


if __name__ == "__main__":
    main()
