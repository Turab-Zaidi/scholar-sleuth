import logging
from opentelemetry import trace, metrics
from opentelemetry.sdk.resources import Resource
# Traces
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
# Metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
# Logs
from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
# Instrumentation
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

# Initialize Providers
resource = Resource.create(attributes={"service.name": "scholarsleuth-server"})

# 1. Traces Setup
trace_provider = TracerProvider(resource=resource)
trace_processor = BatchSpanProcessor(OTLPSpanExporter(endpoint="http://localhost:4317", insecure=True))
trace_provider.add_span_processor(trace_processor)
trace.set_tracer_provider(trace_provider)
tracer = trace.get_tracer("scholarsleuth.server")

# 2. Metrics Setup
metric_reader = PeriodicExportingMetricReader(OTLPMetricExporter(endpoint="http://localhost:4317", insecure=True))
meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
metrics.set_meter_provider(meter_provider)
meter = metrics.get_meter("scholarsleuth.server")

# 3. Logs Setup
logger_provider = LoggerProvider(resource=resource)
log_processor = BatchLogRecordProcessor(OTLPLogExporter(endpoint="http://localhost:4317", insecure=True))
logger_provider.add_log_record_processor(log_processor)
set_logger_provider(logger_provider)

# Set up logging handler to forward python logs to OTel/Loki
otel_logging_handler = LoggingHandler(logger_provider=logger_provider)
logging.getLogger().addHandler(otel_logging_handler)

# Also add a standard console handler to stderr
import sys
console_handler = logging.StreamHandler(sys.stderr)
console_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s'))
logging.getLogger().addHandler(console_handler)

logging.getLogger().setLevel(logging.INFO)

logger = logging.getLogger("scholarsleuth.server")

def instrument_fastapi_app(app):
    """Instrument the FastAPI or Starlette application for tracing request lifecycle."""
    FastAPIInstrumentor.instrument_app(app)
