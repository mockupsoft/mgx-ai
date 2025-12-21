# -*- coding: utf-8 -*-

from __future__ import annotations

import logging
from typing import Optional

from .config import ObservabilityConfig
from .span_store import InMemorySpanExporter, get_span_store

logger = logging.getLogger(__name__)

_INITIALIZED = False


def initialize_otel(
    config: ObservabilityConfig,
    *,
    fastapi_app: Optional[object] = None,
    sqlalchemy_engine: Optional[object] = None,
) -> None:
    """Initialize OpenTelemetry tracing (best-effort).

    This function is safe to call multiple times.
    """

    global _INITIALIZED
    if _INITIALIZED:
        return

    cfg = config.normalized()
    get_span_store().set_maxlen(cfg.span_store_maxlen)

    if not cfg.otel_enabled:
        logger.info("OpenTelemetry disabled")
        _INITIALIZED = True
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
    except Exception as e:
        logger.warning("OpenTelemetry dependencies not available: %s", e)
        _INITIALIZED = True
        return

    resource = Resource.create({"service.name": cfg.service_name})
    sampler = ParentBased(TraceIdRatioBased(cfg.sample_ratio))
    provider = TracerProvider(resource=resource, sampler=sampler)

    provider.add_span_processor(BatchSpanProcessor(InMemorySpanExporter()))

    if cfg.otlp_endpoint:
        exporter = _make_otlp_exporter(cfg)
        if exporter is not None:
            provider.add_span_processor(BatchSpanProcessor(exporter))

    trace.set_tracer_provider(provider)

    _instrument_fastapi(fastapi_app, provider)
    _instrument_sqlalchemy(sqlalchemy_engine)
    _instrument_httpx()
    _instrument_phoenix(cfg)

    _INITIALIZED = True
    logger.info(
        "OpenTelemetry initialized (service=%s, sample_ratio=%.3f, otlp_endpoint=%s)",
        cfg.service_name,
        cfg.sample_ratio,
        cfg.otlp_endpoint,
    )


def _make_otlp_exporter(cfg: ObservabilityConfig):
    headers = None
    if cfg.otlp_headers:
        headers = cfg.otlp_headers

    try:
        if cfg.otlp_protocol == "grpc":
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )

            return OTLPSpanExporter(endpoint=cfg.otlp_endpoint, headers=headers)

        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        return OTLPSpanExporter(endpoint=cfg.otlp_endpoint, headers=headers)
    except Exception as e:
        logger.warning("Failed to initialize OTLP exporter: %s", e)
        return None


def _instrument_fastapi(app: Optional[object], provider) -> None:
    if app is None:
        return

    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
    except Exception as e:
        logger.warning("Failed to instrument FastAPI: %s", e)


def _instrument_sqlalchemy(engine: Optional[object]) -> None:
    if engine is None:
        return

    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

        SQLAlchemyInstrumentor().instrument(engine=engine)
    except Exception as e:
        logger.warning("Failed to instrument SQLAlchemy engine: %s", e)


def _instrument_httpx() -> None:
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument()
    except Exception as e:
        logger.debug("HTTPX instrumentation unavailable: %s", e)


def _instrument_phoenix(cfg: ObservabilityConfig) -> None:
    if not cfg.phoenix_enabled:
        return

    try:
        import phoenix.otel  # type: ignore

        phoenix.otel.register(endpoint=cfg.phoenix_endpoint)
        logger.info("Arize Phoenix OTel integration enabled")
    except Exception as e:
        logger.warning("Failed to enable Arize Phoenix integration: %s", e)
