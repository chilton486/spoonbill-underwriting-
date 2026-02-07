"""Simple in-memory rate limiter for public endpoints.

This is a lightweight MVP implementation suitable for single-instance deployments.
For production with multiple instances, consider using Redis-based rate limiting.
"""
import logging
import time
from collections import defaultdict
from threading import Lock
from typing import Dict, Tuple

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Simple in-memory rate limiter using sliding window.
    
    Tracks requests per IP address and enforces limits.
    """
    
    def __init__(self, max_requests: int = 5, window_seconds: int = 3600):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum number of requests allowed per window
            window_seconds: Time window in seconds (default: 1 hour)
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: Dict[str, list] = defaultdict(list)
        self._lock = Lock()
    
    def _cleanup_old_requests(self, ip: str, current_time: float) -> None:
        """Remove requests outside the current window."""
        cutoff = current_time - self.window_seconds
        self._requests[ip] = [t for t in self._requests[ip] if t > cutoff]
    
    def is_allowed(self, ip: str) -> Tuple[bool, int]:
        """
        Check if a request from the given IP is allowed.
        
        Args:
            ip: Client IP address
            
        Returns:
            Tuple of (is_allowed, remaining_requests)
        """
        current_time = time.time()
        
        with self._lock:
            self._cleanup_old_requests(ip, current_time)
            
            request_count = len(self._requests[ip])
            remaining = max(0, self.max_requests - request_count)
            
            if request_count >= self.max_requests:
                logger.warning(
                    f"Rate limit exceeded for IP {ip}: {request_count} requests in window"
                )
                return False, 0
            
            return True, remaining
    
    def record_request(self, ip: str) -> None:
        """Record a request from the given IP."""
        current_time = time.time()
        
        with self._lock:
            self._requests[ip].append(current_time)
    
    def get_request_count(self, ip: str) -> int:
        """Get current request count for an IP."""
        current_time = time.time()
        
        with self._lock:
            self._cleanup_old_requests(ip, current_time)
            return len(self._requests[ip])


# Global rate limiter instance for application submissions
# 5 requests per hour per IP
application_rate_limiter = RateLimiter(max_requests=5, window_seconds=3600)
