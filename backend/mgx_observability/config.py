# -*- coding: utf-8 -*-

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ObservabilityConfig:
    otel_enabled: bool = False
    service_name: str = "mgx-agent"
    otlp_endpoint: Optional[str] = None
    otlp_protocol: str = "http/protobuf"  # "http/protobuf" | "grpc"
    otlp_headers: Optional[str] = None
    sample_ratio: float = 0.1
    span_store_maxlen: int = 2000

    langsmith_enabled: bool = False
    langsmith_api_key: Optional[str] = None
    langsmith_project: Optional[str] = None
    langsmith_endpoint: Optional[str] = None

    phoenix_enabled: bool = False
    phoenix_endpoint: Optional[str] = None

    def normalized(self) -> "ObservabilityConfig":
        ratio = self.sample_ratio
        if ratio < 0:
            ratio = 0.0
        if ratio > 1:
            ratio = 1.0

        proto = (self.otlp_protocol or "http/protobuf").strip().lower()
        if proto not in {"http/protobuf", "grpc"}:
            proto = "http/protobuf"

        return ObservabilityConfig(
            otel_enabled=bool(self.otel_enabled),
            service_name=self.service_name or "mgx-agent",
            otlp_endpoint=self.otlp_endpoint,
            otlp_protocol=proto,
            otlp_headers=self.otlp_headers,
            sample_ratio=ratio,
            span_store_maxlen=int(self.span_store_maxlen or 2000),
            langsmith_enabled=bool(self.langsmith_enabled),
            langsmith_api_key=self.langsmith_api_key,
            langsmith_project=self.langsmith_project,
            langsmith_endpoint=self.langsmith_endpoint,
            phoenix_enabled=bool(self.phoenix_enabled),
            phoenix_endpoint=self.phoenix_endpoint,
        )
