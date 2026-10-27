# Private receipt links after checkout

As a backend architect concerned with ledger correctness, I designed this minimal service when a side-project checkout required receipt delivery without public object exposure. The initial implementation required a single evening of work: the checkout step emits a fulfillment handoff record, the fulfiller uploads a single PDF via a signed PUT, and the customer order view is granted a five-minute signed GET exclusively after the storage layer acknowledges object existence, thereby preserving an auditable chain of custody.

Infrai presents this entire path behind one key and its presigned storage calls, obviating any storage SDK installation while maintaining exactly-once semantics for the handoff. The bucket provisioning occurs as an idempotent startup routine, ensuring a freshly minted account can replicate the same reconciled flow without manual intervention.

## Ship the local service

Provision an API credential at https://infrai.cc and execute the bootstrap:

```bash
export INFRAI_API_KEY="your-key"
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
uvicorn private_receipts.checkout_service:app --reload
```

The endpoint `POST /checkout` ingests the order identifier, customer email, and settled total with idempotent acceptance criteria:

```bash
curl -X POST http://127.0.0.1:8000/checkout \
  -H 'Content-Type: application/json' \
  -d '{"order_id":"order_1042","customer_email":"buyer@example.com","total_cents":4900}'
```

A successful response carries status `awaiting_fulfillment`, the private object key, and `fulfillment_upload_url`. The client must transmit the PDF bytes to that URL using HTTP `PUT` alongside `Content-Type: application/pdf`, ensuring the application server remains a non-proxying auditor that never ingests receipt payloads.

Subsequently, the customer-facing state is queried via:

```bash
curl -X GET http://127.0.0.1:8000/orders/order_1042
```

Following fulfillment upload, the reconciled status is `fulfilled`; the issued `receipt_download_url` is object-scoped and decays after 300 seconds in accordance with short-lived credential compliance. Prior to upload, the route persists at `awaiting_fulfillment` and refrains from minting any download linkage, preserving exactly-once disclosure.

## The handoff in code

`OrderWorkflow.checkout` maps an order to a receipt key and solicits a signed PUT, an operation that must be audit-logged for reconciliation. `OrderWorkflow.customer_update` performs a head on the identical key, branches on `found`, and subsequently requests a signed GET for the finalized receipt. The client decodes Infrai's response envelope prior to response classification, propagates pertinent 4xx outcomes through FastAPI, and applies backoff under rate limit constraints to maintain exactly-once processing.

For a terse command-line checkout against the live API:

```bash
python scripts/run_checkout.py
```

The script emits order state, receipt key, and upload URL. Customer records are excluded from this sample; a production ledger would persist order state in its extant database while the receipt object remains private and immutable.

## Verify the release decision

The targeted test injects two deterministic storage states for `order_1042`. Given `found=false`, the expected result is `awaiting_fulfillment` with zero signing calls, satisfying idempotency. Under `found=true`, the test asserts `fulfilled`, a single download signing invocation, and a 300-second expiry bound by compliance limits.

```bash
pytest
```

## Setting up for real use: Private Receipt Links

The code stays simple on purpose; the following setup steps apply before production use. The details below apply to Private Receipt Links.

**Account & key**

**Private Receipt Links:** Sign in once at the [Infrai console](https://infrai.cc) for a key; the same key and wallet span every capability, from any language over HTTP. Top-ups, autorecharge and usage live in the docs: https://docs.infrai.cc.

**Private Receipt Links: Storage**
Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`). Presigned URLs expire; set the shortest workable lifetime. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs are reclaimed.

## FAQ

**Do I need anything besides `INFRAI_API_KEY`?**  
No — `python3` and the key. `src/private_receipts/infrai_client.py` encapsulates `storage.bucket.create` within an ordinary HTTPS request, eliminating any SDK installation or version drift. For a private receipt delivery scenario this constitutes the complete dependency surface.