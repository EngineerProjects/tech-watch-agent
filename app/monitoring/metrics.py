"""
Metrics collection system for tech-watch-agent.

This module provides metrics collection and aggregation for monitoring
system performance and usage patterns.

Features:
- Counter metrics for events
- Gauge metrics for current values
- Histogram metrics for distributions
- System resource metrics
"""

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional
import psutil

from app.core.logging import get_logger


logger = get_logger(__name__)


@dataclass
class MetricValue:
    """A single metric value.

    Attributes:
        name: Metric name
        value: Metric value
        labels: Optional labels/tags
        timestamp: When the metric was recorded
    """

    name: str
    value: float
    labels: dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


class MetricsCollector:
    """Collector for application metrics.

    This class provides methods to record and retrieve application metrics
    including counters, gauges, and histograms.

    Usage:
        collector = MetricsCollector()

        # Increment a counter
        collector.increment("newsletter.generated")

        # Record a gauge
        collector.set_gauge("active_connections", 42)

        # Record a histogram value
        collector.observe("request.duration", 0.125)

        # Get all metrics
        metrics = collector.get_all()
    """

    def __init__(self) -> None:
        """Initialize the metrics collector."""
        self._counters: dict[str, float] = {}
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = {}
        self._start_time = time.time()

    def increment(self, name: str, value: float = 1.0) -> None:
        """Increment a counter metric.

        Args:
            name: Metric name
            value: Amount to increment
        """
        if name not in self._counters:
            self._counters[name] = 0.0
        self._counters[name] += value

    def decrement(self, name: str, value: float = 1.0) -> None:
        """Decrement a counter metric.

        Args:
            name: Metric name
            value: Amount to decrement
        """
        if name not in self._counters:
            self._counters[name] = 0.0
        self._counters[name] -= value

    def set_gauge(self, name: str, value: float) -> None:
        """Set a gauge metric to a specific value.

        Args:
            name: Metric name
            value: Gauge value
        """
        self._gauges[name] = value

    def observe(self, name: str, value: float) -> None:
        """Record an observation in a histogram.

        Args:
            name: Metric name
            value: Observed value
        """
        if name not in self._histograms:
            self._histograms[name] = []
        self._histograms[name].append(value)

        # Keep histogram bounded (last 1000 values)
        if len(self._histograms[name]) > 1000:
            self._histograms[name] = self._histograms[name][-1000:]

    def get_counter(self, name: str) -> float:
        """Get current counter value.

        Args:
            name: Metric name

        Returns:
            Counter value or 0 if not exists
        """
        return self._counters.get(name, 0.0)

    def get_gauge(self, name: str) -> Optional[float]:
        """Get current gauge value.

        Args:
            name: Metric name

        Returns:
            Gauge value or None if not exists
        """
        return self._gauges.get(name)

    def get_histogram_stats(self, name: str) -> dict[str, float]:
        """Get histogram statistics.

        Args:
            name: Metric name

        Returns:
            Dictionary with min, max, mean, median, p95, p99
        """
        values = self._histograms.get(name, [])
        if not values:
            return {}

        sorted_values = sorted(values)
        count = len(sorted_values)

        return {
            "count": count,
            "min": sorted_values[0],
            "max": sorted_values[-1],
            "mean": sum(sorted_values) / count,
            "median": sorted_values[count // 2],
            "p95": sorted_values[int(count * 0.95)] if count > 0 else 0,
            "p99": sorted_values[int(count * 0.99)] if count > 0 else 0,
        }

    def get_all(self) -> dict[str, Any]:
        """Get all metrics.

        Returns:
            Dictionary with all metrics by type
        """
        return {
            "counters": self._counters.copy(),
            "gauges": self._gauges.copy(),
            "histograms": {
                name: self.get_histogram_stats(name)
                for name in self._histograms
            },
            "uptime_seconds": time.time() - self._start_time,
        }

    def reset(self) -> None:
        """Reset all metrics."""
        self._counters.clear()
        self._gauges.clear()
        self._histograms.clear()


# Global metrics collector instance
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance.

    Returns:
        Global MetricsCollector instance
    """
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def get_system_metrics() -> dict[str, Any]:
    """Collect system-level metrics.

    Returns:
        Dictionary with system metrics
    """
    try:
        # CPU metrics
        cpu_percent = psutil.cpu_percent(interval=0.1)
        cpu_count = psutil.cpu_count()

        # Memory metrics
        memory = psutil.virtual_memory()

        # Disk metrics
        disk = psutil.disk_usage("/")

        # Network metrics
        network = psutil.net_io_counters()

        # Process metrics
        process = psutil.Process()
        process_memory = process.memory_info()

        return {
            "cpu": {
                "percent": cpu_percent,
                "count": cpu_count,
            },
            "memory": {
                "total_mb": memory.total / (1024 * 1024),
                "used_mb": memory.used / (1024 * 1024),
                "percent": memory.percent,
            },
            "disk": {
                "total_gb": disk.total / (1024 * 1024 * 1024),
                "used_gb": disk.used / (1024 * 1024 * 1024),
                "percent": disk.percent,
            },
            "network": {
                "bytes_sent": network.bytes_sent,
                "bytes_recv": network.bytes_recv,
            },
            "process": {
                "memory_mb": process_memory.rss / (1024 * 1024),
                "cpu_percent": process.cpu_percent(interval=0.1),
                "threads": process.num_threads(),
            },
        }

    except Exception as exc:
        logger.warning("Failed to collect system metrics: %s", exc)
        return {"error": str(exc)}


def record_event(name: str, value: float = 1.0) -> None:
    """Record an event metric.

    Args:
        name: Event name
        value: Event value
    """
    collector = get_metrics_collector()
    collector.increment(name, value)


def record_duration(name: str, duration: float) -> None:
    """Record a duration metric.

    Args:
        name: Metric name
        duration: Duration in seconds
    """
    collector = get_metrics_collector()
    collector.observe(f"{name}.duration", duration)


class MetricsTimer:
    """Context manager for timing operations.

    Usage:
        with MetricsTimer("operation"):
            # Your operation here
            pass
    """

    def __init__(self, name: str) -> None:
        """Initialize timer.

        Args:
            name: Metric name to record duration
        """
        self.name = name
        self.start_time: float = 0.0

    def __enter__(self) -> "MetricsTimer":
        """Start timing."""
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Stop timing and record metric."""
        duration = time.time() - self.start_time
        record_duration(self.name, duration)