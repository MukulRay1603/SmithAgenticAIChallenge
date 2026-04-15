"""
Supabase Realtime listener — bridges Supabase INSERT events on the
window_features table to the local FastAPI risk-scoring endpoint.

Requires SUPABASE_URL, SUPABASE_KEY in environment (or .env).

Usage:
    python -m streaming.stream_listener

Author: Karthik (Gen_Data), integrated by Rahul
"""
import asyncio
import logging
import os

import httpx
from dotenv import load_dotenv
from supabase._async.client import AsyncClient, create_client

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
RISK_AGENT_URL = os.environ.get("RISK_AGENT_URL", "http://localhost:8000/api/ingest")
_http_client: httpx.AsyncClient | None = None


async def _forward_record(record: dict):
    if _http_client is None:
        logger.warning("HTTP client not initialized; dropping streamed row")
        return

    window_id = record.get("window_id")
    try:
        resp = await _http_client.post(RISK_AGENT_URL, json=record)
        resp.raise_for_status()
        result = resp.json()
        logger.info(
            "SCORED  %s → tier=%s score=%.4f",
            window_id,
            result.get("risk_tier"),
            result.get("risk_score", 0),
        )
    except Exception as e:
        logger.warning("Risk agent not reachable for %s: %s", window_id, e)


def on_new_window(payload: dict):
    record = (
        payload.get("data", {}).get("record")
        or payload.get("record")
        or {}
    )
    window_id = record.get("window_id")
    shipment_id = record.get("shipment_id")

    logger.info(
        "STREAM  %s | shipment %s | avg_temp=%s°C | delay=%smin",
        window_id, shipment_id,
        record.get("avg_temp_c"), record.get("current_delay_min"),
    )

    try:
        asyncio.get_running_loop().create_task(_forward_record(record))
    except Exception as e:
        logger.warning("Could not schedule ingest forward for %s: %s", window_id, e)


async def main():
    global _http_client
    if not SUPABASE_URL or not SUPABASE_KEY:
        logger.error("Set SUPABASE_URL and SUPABASE_KEY in environment or .env")
        return

    logger.info("Connecting to Supabase Realtime...")
    sb: AsyncClient = await create_client(SUPABASE_URL, SUPABASE_KEY)
    _http_client = httpx.AsyncClient(timeout=15)

    channel = sb.channel("window-stream")
    channel.on_postgres_changes(
        event="INSERT",
        schema="public",
        table="window_features",
        callback=on_new_window,
    )

    await channel.subscribe()
    logger.info("Subscribed to window_features table. Waiting for rows...")

    try:
        while True:
            await asyncio.sleep(1)
    finally:
        await _http_client.aclose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Listener stopped.")
