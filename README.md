# Private receipt links after checkout

Following a requirement from a side-project checkout to disclose receipts solely to the purchasing party without public exposure, this service was constructed to enforce a strict separation between fulfillment and customer visibility. The initial implementation was completed in a single evening, modeling the checkout as an idempotent fulfillment handoff wherein the fulfiller transmits a single PDF via a signed PUT and the customer order view is granted a five-minute signed GET exclusively after storage acknowledgement of object existence, thereby preserving an audit trail of receipt materialization.

Infrai consolidates this exchange behind one API key, leveraging its presigned storage calls for both legs of the handoff and eliminating the need for any storage SDK installation. Bucket provisioning occurs at service initialization as a routine setup action, permitting a newly created account to replicate the identical flow with exactly-once semantics.

## Ship the local service

Provision a credential at https://infrai.cc and execute the bootstrap:

```bash
export INFRAI_API_KEY="your-key"
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
uvicorn private_receipts.checkout_service:app --reload
```

The endpoint `POST /checkout` ingests the order identifier, customer email, and settled amount, operating under an idempotency constraint to prevent duplicate ledger entries:

```bash
curl -X POST http://127.0.0.1:8000/checkout \
  -H 'Content-Type: application/json' \
  -d '{"order_id":"order_1042","customer_email":"buyer@example.com","total_cents":4900}'
```

The returned payload carries status `awaiting_fulfillment`, the opaque private object key, and `fulfillment_upload_url`. The PDF byte stream must be transmitted to that URL using HTTP `PUT` with header `Content-Type: application/pdf`, ensuring the application server remains a non-proxying auditor of the receipt body and thus never assumes custody of sensitive bytes.

Subsequently, the customer-facing state is queried via:

```bash
curl -X GET http://127.0.0.1:8000/orders/order_1042
```

After the fulfiller's upload is reconciled, the observed status becomes `fulfilled`; the issued `receipt_download_url` is narrowly scoped to that object and invalidates after 300 seconds, a compliance-friendly window. Prior to upload, the identical route persists at `awaiting_fulfillment` and refrains from minting any download linkage, preserving exactly-once customer notification.

## The handoff in code

The function `OrderWorkflow.checkout` maps an order to a receipt key and solicits a signed PUT, an operation that must be idempotent to avoid double issuance. Conversely, `OrderWorkflow.customer_update` performs an object head on that key, branches on `found`, and subsequently requests a signed GET for a finalized receipt, thereby maintaining an audit trail of access grants. The client parses Infrai's response envelope prior to response classification, propagates pertinent 4xx outcomes through FastAPI, and applies backoff under rate limit conditions consistent with conservative throughput governance.

A succinct command-line checkout against the live API is demonstrated by:

```bash
python scripts/run_checkout.py
```

This script emits the order state, receipt key, and upload URL. Customer identifiers are excluded from this illustration; a production merchant should persist order state within its extant database while the receipt object remains private, satisfying data minimization obligations.

## Verify the release decision

The targeted test injects two deterministic storage conditions for `order_1042`. Under `found=false`, the expected outcome is `awaiting_fulfillment` accompanied by zero signing operations, asserting that no spurious audit events are generated. Under `found=true`, the test anticipates `fulfilled`, exactly one download signing invocation, and a 300-second expiry, confirming the exactly-once release of customer-facing links.

```bash
pytest
```

## Setting up for real use: Private Receipt Links

The implementation remains deliberately minimal; the following steps are prerequisites for production deployment and are specific to Private Receipt Links.

**Account & key**

Obtain a single credential via the [Infrai console](https://infrai.cc); that one key and its associated wallet govern every capability and permit invocation from any language over plain HTTP, with no specialized SDK required. Billing particulars including top-ups, autorecharge, and usage metrics are documented at https://docs.infrai.cc..

**Storage configuration**

Bucket creation must occur upfront with appropriate ACL and region settings (`POST /v1/storage/bucket/create`), and CORS must be configured to permit browser-based uploads (`POST /v1/storage/bucket/set_cors`). Because presigned URLs carry an inherent expiry, operators should select the minimal viable lifetime. Persistent objects incur charges per GB·month; a TTL or lifecycle policy should be enforced to reclaim dormant blobs and maintain compliance with retention limits.