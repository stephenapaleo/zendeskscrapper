"""Rate limiting utility for API requests."""
import time
import threading
from typing import Callable, Any
from functools import wraps
from collections import deque
from datetime import datetime, timedelta

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import requests


class RateLimiter:
    """Rate limiter that enforces requests per minute limits."""
    
    def __init__(self, requests_per_minute: int = 700):
        """Initialize rate limiter.
        
        Args:
            requests_per_minute: Maximum number of requests per minute
        """
        self.requests_per_minute = requests_per_minute
        self.min_interval = 60.0 / requests_per_minute  # Minimum seconds between requests
        self.request_times = deque()
        self.lock = threading.Lock()
    
    def wait_if_needed(self):
        """Wait if necessary to respect rate limits."""
        with self.lock:
            now = datetime.now()
            
            # Remove requests older than 1 minute
            while self.request_times and now - self.request_times[0] > timedelta(minutes=1):
                self.request_times.popleft()
            
            # If we're at the limit, wait until we can make another request
            if len(self.request_times) >= self.requests_per_minute:
                sleep_time = (self.request_times[0] + timedelta(minutes=1) - now).total_seconds()
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    # Remove the old request after waiting
                    self.request_times.popleft()
            
            # Record this request
            self.request_times.append(now)


class APIRateLimiter:
    """Enhanced rate limiter with retry logic for API calls."""
    
    def __init__(self, requests_per_minute: int = 700, retry_attempts: int = 3, backoff_factor: int = 2):
        """Initialize API rate limiter.
        
        Args:
            requests_per_minute: Maximum requests per minute
            retry_attempts: Number of retry attempts for failed requests
            backoff_factor: Exponential backoff factor
        """
        self.rate_limiter = RateLimiter(requests_per_minute)
        self.retry_attempts = retry_attempts
        self.backoff_factor = backoff_factor
    
    def __call__(self, func: Callable) -> Callable:
        """Decorator to apply rate limiting and retry logic to functions.
        
        Args:
            func: Function to decorate
            
        Returns:
            Decorated function with rate limiting and retry logic
        """
        @wraps(func)
        @retry(
            stop=stop_after_attempt(self.retry_attempts),
            wait=wait_exponential(multiplier=1, min=4, max=10),
            retry=retry_if_exception_type((
                requests.exceptions.RequestException,
                requests.exceptions.HTTPError,
                requests.exceptions.ConnectionError,
                requests.exceptions.Timeout
            ))
        )
        def wrapper(*args, **kwargs) -> Any:
            # Check if this is a rate limit error (429)
            try:
                result = func(*args, **kwargs)
                # If we get a response object, check for rate limiting
                if hasattr(result, 'status_code') and result.status_code == 429:
                    retry_after = int(result.headers.get('Retry-After', 60))
                    print(f"Rate limit exceeded. Waiting {retry_after} seconds...")
                    time.sleep(retry_after)
                    raise requests.exceptions.HTTPError("Rate limit exceeded", response=result)
                return result
            except requests.exceptions.HTTPError as e:
                if hasattr(e, 'response') and e.response.status_code == 429:
                    retry_after = int(e.response.headers.get('Retry-After', 60))
                    print(f"Rate limit exceeded. Waiting {retry_after} seconds...")
                    time.sleep(retry_after)
                raise
        
        return wrapper
    
    def limit_request(self, func: Callable) -> Callable:
        """Apply only rate limiting without retry logic.
        
        Args:
            func: Function to decorate
            
        Returns:
            Function with rate limiting applied
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            self.rate_limiter.wait_if_needed()
            return func(*args, **kwargs)
        
        return wrapper


def rate_limited_request(requests_per_minute: int = 700, retry_attempts: int = 3):
    """Decorator factory for rate-limited API requests.
    
    Args:
        requests_per_minute: Maximum requests per minute
        retry_attempts: Number of retry attempts
        
    Returns:
        Decorator function
    """
    limiter = APIRateLimiter(requests_per_minute, retry_attempts)
    return limiter 