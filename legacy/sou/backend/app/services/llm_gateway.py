from __future__ import annotations

import json
import time

from openai import OpenAI
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import ApiUsageLog, NormalizedDocument
from app.schemas.event import ExtractedEvent
from app.services.collectors.base import ConnectorUnconfigured


class LLMGateway:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()

    def extract_event(self, document: NormalizedDocument) -> ExtractedEvent:
        if self.settings.llm_provider != "openai" or not self.settings.openai_api_key:
            raise ConnectorUnconfigured("openai", "OPENAI_API_KEY is not configured")
        client = OpenAI(api_key=self.settings.openai_api_key)
        schema = ExtractedEvent.model_json_schema()
        prompt = (
            "Extract one intelligence event from the document. Use only evidence present in the "
            "document. If the document lacks a verifiable event, return category 'other', low "
            "confidence, and mark claims needing verification.\n\n"
            f"Document ID: {document.id}\n"
            f"Title: {document.title}\n"
            f"URL: {document.canonical_url}\n"
            f"Text: {document.clean_text[:6000]}"
        )
        last_error: Exception | None = None
        for attempt in range(2):
            started = time.perf_counter()
            status = "error"
            try:
                response = client.responses.create(
                    model=self.settings.openai_model,
                    input=prompt,
                    text={
                        "format": {
                            "type": "json_schema",
                            "name": "extracted_event",
                            "schema": schema,
                            "strict": True,
                        }
                    },
                )
                payload = json.loads(response.output_text)
                event = ExtractedEvent.model_validate(payload)
                status = "ok"
                return event
            except (ValidationError, json.JSONDecodeError, Exception) as exc:
                last_error = exc
                if attempt == 1:
                    raise
            finally:
                latency_ms = int((time.perf_counter() - started) * 1000)
                self.db.add(
                    ApiUsageLog(
                        provider="openai",
                        operation="extract_event",
                        status=status,
                        latency_ms=latency_ms,
                        cost_estimate=0.0,
                        metadata_={"document_id": document.id},
                    )
                )
                self.db.commit()
        raise RuntimeError(str(last_error))
