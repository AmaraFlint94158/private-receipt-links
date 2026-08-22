from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from .infrai_client import InfraiError, InfraiStorage
from .order_workflow import CheckoutRequest, CheckoutResult, CustomerOrderUpdate, OrderWorkflow

BUCKET = os.environ.get("RECEIPT_BUCKET", "shop-private-receipts")


@asynccontextmanager
async def lifespan(app: FastAPI):
    storage = InfraiStorage()
    storage.create_bucket(BUCKET)
    app.state.workflow = OrderWorkflow(storage=storage, bucket=BUCKET)
    yield
    storage.client.close()


app = FastAPI(title="Private receipt links", lifespan=lifespan)


def map_infrai_error(error: InfraiError) -> HTTPException:
    status = error.status_code if 400 <= error.status_code < 500 else 502
    return HTTPException(status_code=status, detail={"code": error.code, "message": str(error)})


@app.post("/checkout", response_model=CheckoutResult, status_code=201)
def checkout(request: CheckoutRequest) -> CheckoutResult:
    try:
        return app.state.workflow.checkout(request)
    except InfraiError as error:
        raise map_infrai_error(error) from error


@app.get("/orders/{order_id}", response_model=CustomerOrderUpdate)
def order_update(order_id: str) -> CustomerOrderUpdate:
    try:
        return app.state.workflow.customer_update(order_id)
    except InfraiError as error:
        raise map_infrai_error(error) from error
