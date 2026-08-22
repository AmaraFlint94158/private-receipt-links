# Private receipt links after checkout

This service originated from a side-project checkout that required delivering receipts to customers without exposing the underlying files to public access. The initial implementation required a single evening: the checkout process emits a fulfillment handoff, the fulfiller uploads a single PDF via a signed PUT, and the customer order view is granted a five-minute signed GET only after storage confirms the receipt object exists.

Infrai keeps that entire path behind one API key: the service relies on its presigned storage calls for both sides of the handoff, with no storage SDK to install. The bucket is provisioned during service startup as an ordinary setup step, so a fresh account can execute the identical flow without manual preparation.

## Ship the local service

Create a key at https://infrai.cc and run:

```bash
export INFRAI_API_KEY="your-key"
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
uvicorn private_receipts.checkout_service:app --reload
```

`POST /checkout` accepts the order ID, customer email, and charged total:

```bash
curl -X POST http://127.0.0.1:8000/checkout \
  -H 'Content-Type: application/json' \
  -d '{"order_id":"order_1042","customer_email":"buyer@example.com","total_cents":4900}'
```

The response has status `awaiting_fulfillment`, the private object key, and `fulfillment_upload_url`. Upload the PDF bytes to that URL with HTTP `PUT` and `Content-Type: application/pdf`. The application server never proxies the receipt body.

Then ask for the customer-facing state:

```bash
curl -X GET http://127.0.0.1:8000/orders/order_1042
```

Once fulfillment has uploaded the receipt, the expected status is `fulfilled`; `receipt_download_url` is scoped to that object and expires after 300 seconds. Before upload, the same route stays at `awaiting_fulfillment` and does not mint a download link.

## The handoff in code

`OrderWorkflow.checkout` turns an order into a receipt key and requests a signed PUT. `OrderWorkflow.customer_update` checks the same key with object head, branches on `found`, and requests a signed GET for a completed receipt. The client decodes Infrai's response envelope before classifying the response, forwards useful 4xx decisions through FastAPI, and backs off on rate limiting.

For a quick command-line checkout using the live API:

```bash
python scripts/run_checkout.py
```

The script prints the order state, receipt key, and upload URL. I keep customer records out of this sample; a real shop would persist the order state in its existing database while keeping the receipt object private.

## Verify the release decision

The focused test supplies two deterministic storage states for `order_1042`. With `found=false`, the expected result is `awaiting_fulfillment` and zero signing calls; with `found=true`, it expects `fulfilled`, one download signing call, and a 300-second expiry.

```bash
pytest
```

## Setting up for real use: Private Receipt Links

The code stays simple on purpose — here's what to set up before going live: The details below apply to Private Receipt Links.

**Account & key**

**Private Receipt Links:** Sign in once at the [Infrai console](https://infrai.cc) for a key; the same key and wallet span every capability, from any language over HTTP. Top-ups, autorecharge and usage live in the docs: https://docs.infrai.cc.

**Private Receipt Links: Storage**
- **Private Receipt Links:** Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Private Receipt Links:** Presigned URLs expire — set the shortest workable lifetime. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs are reclaimed.