"""
LLM Monitoring Service

Handles token tracking, cost calculation, and rate limiting for LLM usage.
"""

import time
from typing import Dict, Any
from collections import deque
from datetime import datetime, timedelta
import os


class TokenBucket:
    """
    Token bucket algorithm for rate limiting
    
    Allows bursts but enforces average rate over time
    """
    
    def __init__(self, capacity: int, refill_rate: float):
        """
        Args:
            capacity: Maximum tokens in bucket
            refill_rate: Tokens added per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = time.time()
    
    def consume(self, tokens: int) -> bool:
        """
        Try to consume tokens from bucket
        
        Returns:
            True if tokens consumed, False if rate limit exceeded
        """
        self._refill()
        
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False
    
    def _refill(self):
        """Refill tokens based on elapsed time"""
        now = time.time()
        elapsed = now - self.last_refill
        refill_amount = elapsed * self.refill_rate
        
        self.tokens = min(self.capacity, self.tokens + refill_amount)
        self.last_refill = now
    
    def time_until_available(self, tokens: int) -> float:
        """
        Calculate seconds until enough tokens available
        
        Args:
            tokens: Number of tokens needed
            
        Returns:
            Seconds to wait (0 if available now)
        """
        self._refill()
        
        if self.tokens >= tokens:
            return 0.0
        
        deficit = tokens - self.tokens
        return deficit / self.refill_rate


class CostCalculator:
    """
    Calculate LLM API costs based on token usage
    
    Pricing as of 2024 (USD per 1M tokens)
    """
    
    # Pricing per 1M tokens (input / output)
    PRICING = {
        "openai": {
            "gpt-4-turbo-preview": {"input": 10.00, "output": 30.00},
            "gpt-4-turbo": {"input": 10.00, "output": 30.00},
            "gpt-4o": {"input": 2.50, "output": 10.00},
            "gpt-4": {"input": 30.00, "output": 60.00},
            "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
        },
        "anthropic": {
            "claude-3-5-sonnet-20241022": {"input": 3.00, "output": 15.00},
            "claude-3-opus-20240229": {"input": 15.00, "output": 75.00},
            "claude-3-sonnet-20240229": {"input": 3.00, "output": 15.00},
            "claude-3-haiku-20240307": {"input": 0.25, "output": 1.25},
        },
        "google": {
            "gemini-2.5-flash": {"input": 0.075, "output": 0.30},
            "gemini-pro": {"input": 0.50, "output": 1.50},
            "gemini-pro-vision": {"input": 0.50, "output": 1.50},
        }
    }
    
    @classmethod
    def calculate_cost(
        cls,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int
    ) -> float:
        """
        Calculate cost in USD
        
        Args:
            provider: LLM provider (openai/anthropic/google)
            model: Model name
            input_tokens: Input token count
            output_tokens: Output token count
            
        Returns:
            Cost in USD
        """
        provider = provider.lower()
        
        # Get pricing for model
        if provider not in cls.PRICING:
            return 0.0
        
        if model not in cls.PRICING[provider]:
            # Try to find similar model
            for known_model in cls.PRICING[provider]:
                if known_model in model or model in known_model:
                    model = known_model
                    break
            else:
                return 0.0
        
        pricing = cls.PRICING[provider][model]
        
        # Calculate cost per token
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        
        return input_cost + output_cost


class LLMMonitoringService:
    """
    Monitor LLM usage with token tracking, cost calculation, and rate limiting
    """
    
    def __init__(self):
        # Rate limiting
        self.request_limiter = self._create_request_limiter()
        self.token_limiter = self._create_token_limiter()
        
        # Usage tracking
        self.requests_history = deque(maxlen=1000)
        self.daily_costs = {}
        
        # Cost limits
        self.max_cost_per_request = float(os.getenv("MAX_COST_PER_REQUEST", "1.0"))
        self.daily_spending_limit = float(os.getenv("DAILY_SPENDING_LIMIT", "100.0"))
    
    def _create_request_limiter(self) -> TokenBucket:
        """Create rate limiter for requests per minute"""
        max_rpm = int(os.getenv("MAX_REQUESTS_PER_MINUTE", "60"))
        return TokenBucket(
            capacity=max_rpm,
            refill_rate=max_rpm / 60.0  # Refill per second
        )
    
    def _create_token_limiter(self) -> TokenBucket:
        """Create rate limiter for tokens per minute"""
        max_tpm = int(os.getenv("MAX_TOKENS_PER_MINUTE", "150000"))
        return TokenBucket(
            capacity=max_tpm,
            refill_rate=max_tpm / 60.0  # Refill per second
        )
    
    def check_rate_limits(self, estimated_tokens: int = 1000) -> Dict[str, Any]:
        """
        Check if request would exceed rate limits
        
        Args:
            estimated_tokens: Estimated token usage for request
            
        Returns:
            Dict with status and retry_after if limited
        """
        # Check request rate limit
        if not self.request_limiter.consume(1):
            wait_time = self.request_limiter.time_until_available(1)
            return {
                "allowed": False,
                "reason": "requests_per_minute",
                "retry_after": wait_time
            }
        
        # Check token rate limit
        if not self.token_limiter.consume(estimated_tokens):
            wait_time = self.token_limiter.time_until_available(estimated_tokens)
            # Refund the request token since we're denying
            self.request_limiter.tokens = min(
                self.request_limiter.capacity,
                self.request_limiter.tokens + 1
            )
            return {
                "allowed": False,
                "reason": "tokens_per_minute",
                "retry_after": wait_time
            }
        
        return {"allowed": True}
    
    def track_usage(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        duration_seconds: float
    ) -> Dict[str, Any]:
        """
        Track LLM usage and calculate cost
        
        Args:
            provider: LLM provider
            model: Model name
            input_tokens: Input token count
            output_tokens: Output token count
            duration_seconds: Request duration
            
        Returns:
            Usage metrics including cost
        """
        total_tokens = input_tokens + output_tokens
        cost = CostCalculator.calculate_cost(provider, model, input_tokens, output_tokens)
        
        # Track daily spending
        today = datetime.now().date().isoformat()
        if today not in self.daily_costs:
            self.daily_costs[today] = 0.0
        self.daily_costs[today] += cost
        
        # Store in history
        usage_record = {
            "timestamp": datetime.now().isoformat(),
            "provider": provider,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "cost_usd": cost,
            "duration_seconds": duration_seconds,
        }
        self.requests_history.append(usage_record)
        
        # Check if over daily limit
        daily_total = self.daily_costs[today]
        over_daily_limit = daily_total > self.daily_spending_limit
        
        # Check if single request exceeded limit
        over_request_limit = cost > self.max_cost_per_request
        
        return {
            **usage_record,
            "daily_total_cost": daily_total,
            "daily_limit": self.daily_spending_limit,
            "over_daily_limit": over_daily_limit,
            "over_request_limit": over_request_limit,
        }
    
    def check_cost_limits(self, estimated_cost: float) -> Dict[str, Any]:
        """
        Check if request would exceed cost limits
        
        Args:
            estimated_cost: Estimated cost in USD
            
        Returns:
            Dict with allowed status and reason
        """
        # Check single request limit
        if estimated_cost > self.max_cost_per_request:
            return {
                "allowed": False,
                "reason": "max_cost_per_request",
                "limit": self.max_cost_per_request,
                "estimated_cost": estimated_cost
            }
        
        # Check daily spending limit
        today = datetime.now().date().isoformat()
        daily_total = self.daily_costs.get(today, 0.0)
        
        if daily_total + estimated_cost > self.daily_spending_limit:
            return {
                "allowed": False,
                "reason": "daily_spending_limit",
                "limit": self.daily_spending_limit,
                "daily_total": daily_total,
                "estimated_cost": estimated_cost
            }
        
        return {"allowed": True}
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get usage statistics
        
        Returns:
            Statistics summary
        """
        if not self.requests_history:
            return {
                "total_requests": 0,
                "total_tokens": 0,
                "total_cost": 0.0,
                "average_cost": 0.0,
                "daily_costs": {}
            }
        
        total_requests = len(self.requests_history)
        total_tokens = sum(r["total_tokens"] for r in self.requests_history)
        total_cost = sum(r["cost_usd"] for r in self.requests_history)
        
        # Get recent stats (last hour)
        one_hour_ago = datetime.now() - timedelta(hours=1)
        recent_requests = [
            r for r in self.requests_history
            if datetime.fromisoformat(r["timestamp"]) > one_hour_ago
        ]
        
        return {
            "total_requests": total_requests,
            "total_tokens": total_tokens,
            "total_cost": round(total_cost, 4),
            "average_cost": round(total_cost / total_requests, 4) if total_requests > 0 else 0.0,
            "recent_hour": {
                "requests": len(recent_requests),
                "tokens": sum(r["total_tokens"] for r in recent_requests),
                "cost": round(sum(r["cost_usd"] for r in recent_requests), 4)
            },
            "daily_costs": {k: round(v, 4) for k, v in self.daily_costs.items()},
            "rate_limits": {
                "requests_per_minute": int(os.getenv("MAX_REQUESTS_PER_MINUTE", "60")),
                "tokens_per_minute": int(os.getenv("MAX_TOKENS_PER_MINUTE", "150000")),
                "max_cost_per_request": self.max_cost_per_request,
                "daily_spending_limit": self.daily_spending_limit
            }
        }
