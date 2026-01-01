"""
Metrics Service để track và monitor hệ thống
Sử dụng Prometheus metrics và structured logging
"""
import os
import time
import logging
from typing import Optional, Dict, Any
from functools import wraps
from contextlib import contextmanager
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Prometheus metrics (lazy initialization)
_prometheus_available = False
_metrics = {}

def _init_prometheus():
    """Initialize Prometheus metrics"""
    global _prometheus_available, _metrics
    
    if _prometheus_available:
        return _metrics
    
    try:
        from prometheus_client import Counter, Histogram, Gauge, Summary
        from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
        
        # Request metrics
        _metrics['http_requests_total'] = Counter(
            'http_requests_total',
            'Total HTTP requests',
            ['method', 'endpoint', 'status']
        )
        
        _metrics['http_request_duration_seconds'] = Histogram(
            'http_request_duration_seconds',
            'HTTP request duration in seconds',
            ['method', 'endpoint'],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
        )
        
        # LLM metrics
        _metrics['llm_requests_total'] = Counter(
            'llm_requests_total',
            'Total LLM requests',
            ['provider', 'status']
        )
        
        _metrics['llm_request_duration_seconds'] = Histogram(
            'llm_request_duration_seconds',
            'LLM request duration in seconds',
            ['provider'],
            buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0]
        )
        
        _metrics['llm_tokens_total'] = Counter(
            'llm_tokens_total',
            'Total LLM tokens used',
            ['provider', 'type']  # type: input, output
        )
        
        # Embedding metrics
        _metrics['embedding_requests_total'] = Counter(
            'embedding_requests_total',
            'Total embedding generation requests',
            ['provider', 'status']
        )
        
        _metrics['embedding_duration_seconds'] = Histogram(
            'embedding_duration_seconds',
            'Embedding generation duration in seconds',
            ['provider'],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0]
        )
        
        # Database metrics
        _metrics['db_queries_total'] = Counter(
            'db_queries_total',
            'Total database queries',
            ['operation', 'status']
        )
        
        _metrics['db_query_duration_seconds'] = Histogram(
            'db_query_duration_seconds',
            'Database query duration in seconds',
            ['operation'],
            buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0]
        )
        
        # Cache metrics
        _metrics['cache_hits_total'] = Counter(
            'cache_hits_total',
            'Total cache hits',
            ['cache_type', 'level']  # level: l1, l2, l3
        )
        
        _metrics['cache_misses_total'] = Counter(
            'cache_misses_total',
            'Total cache misses',
            ['cache_type']
        )
        
        _metrics['cache_sets_total'] = Counter(
            'cache_sets_total',
            'Total cache sets',
            ['cache_type', 'level']
        )
        
        _metrics['cache_evictions_total'] = Counter(
            'cache_evictions_total',
            'Total cache evictions',
            ['level']
        )
        
        _metrics['cache_size'] = Gauge(
            'cache_size',
            'Current cache size',
            ['level']
        )
        
        _metrics['cache_ttl_seconds'] = Histogram(
            'cache_ttl_seconds',
            'Cache TTL in seconds',
            ['cache_type', 'level'],
            buckets=[60, 300, 600, 1800, 3600, 7200, 14400, 28800, 86400]
        )
        
        # Error metrics
        _metrics['errors_total'] = Counter(
            'errors_total',
            'Total errors',
            ['error_type', 'service']
        )
        
        # System metrics
        _metrics['active_connections'] = Gauge(
            'active_connections',
            'Number of active connections',
            ['type']
        )
        
        _prometheus_available = True
        logger.info("Prometheus metrics initialized")
        
        return _metrics
        
    except ImportError:
        logger.warning("prometheus_client not installed. Install with: pip install prometheus-client")
        _prometheus_available = False
        return {}
    except Exception as e:
        logger.error(f"Failed to initialize Prometheus metrics: {e}")
        _prometheus_available = False
        return {}

def get_metrics():
    """Get Prometheus metrics instance"""
    return _init_prometheus()

def get_metrics_export():
    """Get Prometheus metrics export (for /metrics endpoint)"""
    if not _prometheus_available:
        return None
    
    try:
        from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
        return generate_latest(), CONTENT_TYPE_LATEST
    except Exception as e:
        logger.error(f"Failed to generate metrics export: {e}")
        return None

class MetricsService:
    """Service để track metrics và monitoring"""
    
    def __init__(self):
        self.metrics = get_metrics()
        self.enabled = _prometheus_available
        
        if not self.enabled:
            logger.info("Metrics are disabled (Prometheus not available)")
    
    def record_http_request(self, method: str, endpoint: str, status_code: int, duration: float):
        """Record HTTP request metrics"""
        if not self.enabled:
            return
        
        try:
            # Normalize endpoint (remove IDs)
            normalized_endpoint = self._normalize_endpoint(endpoint)
            
            self.metrics['http_requests_total'].labels(
                method=method,
                endpoint=normalized_endpoint,
                status=str(status_code)
            ).inc()
            
            self.metrics['http_request_duration_seconds'].labels(
                method=method,
                endpoint=normalized_endpoint
            ).observe(duration)
        except Exception as e:
            logger.warning(f"Failed to record HTTP metrics: {e}")
    
    def record_llm_request(self, provider: str, status: str, duration: float, 
                          input_tokens: Optional[int] = None, 
                          output_tokens: Optional[int] = None):
        """Record LLM request metrics"""
        if not self.enabled:
            return
        
        try:
            self.metrics['llm_requests_total'].labels(
                provider=provider,
                status=status
            ).inc()
            
            self.metrics['llm_request_duration_seconds'].labels(
                provider=provider
            ).observe(duration)
            
            if input_tokens:
                self.metrics['llm_tokens_total'].labels(
                    provider=provider,
                    type='input'
                ).inc(input_tokens)
            
            if output_tokens:
                self.metrics['llm_tokens_total'].labels(
                    provider=provider,
                    type='output'
                ).inc(output_tokens)
        except Exception as e:
            logger.warning(f"Failed to record LLM metrics: {e}")
    
    def record_embedding_request(self, provider: str, status: str, duration: float):
        """Record embedding generation metrics"""
        if not self.enabled:
            return
        
        try:
            self.metrics['embedding_requests_total'].labels(
                provider=provider,
                status=status
            ).inc()
            
            self.metrics['embedding_duration_seconds'].labels(
                provider=provider
            ).observe(duration)
        except Exception as e:
            logger.warning(f"Failed to record embedding metrics: {e}")
    
    def record_db_query(self, operation: str, status: str, duration: float):
        """Record database query metrics"""
        if not self.enabled:
            return
        
        try:
            self.metrics['db_queries_total'].labels(
                operation=operation,
                status=status
            ).inc()
            
            self.metrics['db_query_duration_seconds'].labels(
                operation=operation
            ).observe(duration)
        except Exception as e:
            logger.warning(f"Failed to record DB metrics: {e}")
    
    def record_cache_hit(self, cache_type: str, level: str = "unknown"):
        """Record cache hit"""
        if not self.enabled:
            return
        
        try:
            # Handle format "level:cache_type" or separate params
            if ":" in cache_type:
                level, cache_type = cache_type.split(":", 1)
            
            self.metrics['cache_hits_total'].labels(
                cache_type=cache_type,
                level=level
            ).inc()
        except Exception as e:
            logger.warning(f"Failed to record cache hit: {e}")
    
    def record_cache_miss(self, cache_type: str):
        """Record cache miss"""
        if not self.enabled:
            return
        
        try:
            self.metrics['cache_misses_total'].labels(cache_type=cache_type).inc()
        except Exception as e:
            logger.warning(f"Failed to record cache miss: {e}")
    
    def record_cache_set(self, cache_type: str, level: str = "unknown"):
        """Record cache set"""
        if not self.enabled:
            return
        
        try:
            self.metrics['cache_sets_total'].labels(
                cache_type=cache_type,
                level=level
            ).inc()
        except Exception as e:
            logger.warning(f"Failed to record cache set: {e}")
    
    def record_cache_eviction(self, level: str = "unknown"):
        """Record cache eviction"""
        if not self.enabled:
            return
        
        try:
            self.metrics['cache_evictions_total'].labels(level=level).inc()
        except Exception as e:
            logger.warning(f"Failed to record cache eviction: {e}")
    
    def update_cache_size(self, level: str, size: int):
        """Update cache size gauge"""
        if not self.enabled:
            return
        
        try:
            self.metrics['cache_size'].labels(level=level).set(size)
        except Exception as e:
            logger.warning(f"Failed to update cache size: {e}")
    
    def record_cache_ttl(self, cache_type: str, level: str, ttl: float):
        """Record cache TTL"""
        if not self.enabled:
            return
        
        try:
            self.metrics['cache_ttl_seconds'].labels(
                cache_type=cache_type,
                level=level
            ).observe(ttl)
        except Exception as e:
            logger.warning(f"Failed to record cache TTL: {e}")
    
    def record_error(self, error_type: str, service: str):
        """Record error"""
        if not self.enabled:
            return
        
        try:
            self.metrics['errors_total'].labels(
                error_type=error_type,
                service=service
            ).inc()
        except Exception as e:
            logger.warning(f"Failed to record error: {e}")
    
    def _normalize_endpoint(self, endpoint: str) -> str:
        """Normalize endpoint path (remove IDs, etc.)"""
        import re
        # Replace UUIDs and numbers with placeholders
        endpoint = re.sub(r'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '/{id}', endpoint)
        endpoint = re.sub(r'/\d+', '/{id}', endpoint)
        return endpoint
    
    @contextmanager
    def track_operation(self, operation_type: str, **labels):
        """Context manager để track operation duration"""
        start_time = time.time()
        try:
            yield
            duration = time.time() - start_time
            status = 'success'
        except Exception as e:
            duration = time.time() - start_time
            status = 'error'
            self.record_error(type(e).__name__, operation_type)
            raise
        finally:
            if operation_type == 'llm':
                provider = labels.get('provider', 'unknown')
                self.record_llm_request(provider, status, duration)
            elif operation_type == 'embedding':
                provider = labels.get('provider', 'unknown')
                self.record_embedding_request(provider, status, duration)
            elif operation_type == 'db':
                operation = labels.get('operation', 'unknown')
                self.record_db_query(operation, status, duration)

# Global metrics service instance
metrics_service = MetricsService()