import base64
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from google.api_core.exceptions import NotFound
from google.cloud import bigquery


BQ_DATASET = os.environ.get("BQ_DATASET", "hpsu")
BQ_TABLE = os.environ.get("BQ_TABLE", "readings")
BQ_LOCATION = os.environ.get("BQ_LOCATION")  # optional, e.g., "EU"

_bq_client: bigquery.Client | None = None
_table_ref: bigquery.TableReference | None = None


def _get_bq_client() -> bigquery.Client:
    global _bq_client
    if _bq_client is None:
        _bq_client = bigquery.Client(location=BQ_LOCATION) if BQ_LOCATION else bigquery.Client()
    return _bq_client


def _get_table_ref() -> bigquery.TableReference:
    global _table_ref
    if _table_ref is None:
        client = _get_bq_client()
        dataset_ref = client.dataset(BQ_DATASET)
        _table_ref = dataset_ref.table(BQ_TABLE)
    return _table_ref


def _ensure_table_exists() -> None:
    client = _get_bq_client()
    table_ref = _get_table_ref()
    try:
        client.get_table(table_ref)
        return
    except NotFound:
        pass

    # Create dataset if needed
    try:
        client.get_dataset(table_ref.dataset_id)
    except NotFound:
        ds = bigquery.Dataset(table_ref.dataset)
        if BQ_LOCATION:
            ds.location = BQ_LOCATION
        client.create_dataset(ds, exists_ok=True)

    schema = [
        bigquery.SchemaField("event_time", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("message_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("metric", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("value", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("src_time", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("ingested_at", "TIMESTAMP", mode="REQUIRED"),
    ]
    table = bigquery.Table(table_ref, schema=schema)
    client.create_table(table, exists_ok=True)


def _parse_pubsub_message(event: Dict[str, Any]) -> Dict[str, Any]:
    data_b64 = event.get("data", "")
    if not data_b64:
        return {}
    raw = base64.b64decode(data_b64).decode("utf-8")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        # Accept plain text and wrap
        payload = {"raw": raw}
    return payload


def _rows_from_payload(payload: Dict[str, Any], event_time: datetime, message_id: str) -> tuple[List[Dict[str, Any]], List[str]]:
    rows: List[Dict[str, Any]] = []
    row_ids: List[str] = []

    src_time = None
    if isinstance(payload.get("time"), str):
        src_time = payload.get("time")

    # One row per metric key (excluding reserved keys)
    reserved_keys = {"time"}
    now_iso = datetime.now(timezone.utc).isoformat()
    for k, v in payload.items():
        if k in reserved_keys:
            continue
        rows.append(
            {
                "event_time": event_time.isoformat(),
                "message_id": message_id,
                "metric": str(k),
                "value": json.dumps(v) if not isinstance(v, (str, int, float, bool)) else str(v),
                "src_time": src_time,
                "ingested_at": now_iso,
            }
        )
        row_ids.append(f"{message_id}-{k}")

    # If there were no metrics, still record a stub row
    if not rows:
        rows.append(
            {
                "event_time": event_time.isoformat(),
                "message_id": message_id,
                "metric": "_empty",
                "value": json.dumps(payload),
                "src_time": src_time,
                "ingested_at": now_iso,
            }
        )
        row_ids.append(f"{message_id}-_empty")

    return rows, row_ids


# Entry point for a background (Pub/Sub) function
# Gen1 and Gen2 both support this signature with --trigger-topic
def handle_pubsub(event, context):
    _ensure_table_exists()

    message_id = getattr(context, "event_id", None) or getattr(context, "eventId", None) or "unknown"
    event_time_str = getattr(context, "timestamp", None) or getattr(context, "timestamp", None)
    try:
        event_time = datetime.fromisoformat(event_time_str.replace("Z", "+00:00")) if event_time_str else datetime.now(timezone.utc)
    except Exception:
        event_time = datetime.now(timezone.utc)

    payload = _parse_pubsub_message(event)
    rows, row_ids = _rows_from_payload(payload, event_time, message_id)

    client = _get_bq_client()
    errors = client.insert_rows_json(_get_table_ref(), rows, row_ids=row_ids)
    if errors:
        # Raising will trigger retry/DLQ at subscription level
        raise RuntimeError(f"BigQuery insert errors: {errors}")

    return "ok"
