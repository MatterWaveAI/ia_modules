"""
Unit Tests for LLM Monitoring Service

Tests token tracking, cost calculation, and rate limiting functionality.
"""

import pytest
import time

from services.llm_monitoring_service import (
    LLMMonitoringService,
    CostCalculator,
    TokenBucket
)


class TestTokenBucket:
    """Test token bucket rate limiting algorithm"""
    
    def test_initial_capacity(self):
        """Bucket starts at full capacity"""
        bucket = TokenBucket(capacity=100, refill_rate=10)
        assert bucket.tokens == 100
    
    def test_consume_tokens(self):
        """Can consume tokens when available"""
        bucket = TokenBucket(capacity=100, refill_rate=10)
        assert bucket.consume(50) is True
        assert bucket.tokens == 50
    
    def test_exceed_capacity(self):
        """Cannot consume more tokens than available"""
        bucket = TokenBucket(capacity=100, refill_rate=10)
        assert bucket.consume(150) is False
        assert bucket.tokens == 100  # No tokens consumed
    
    def test_refill_over_time(self):
        """Tokens refill based on rate"""
        bucket = TokenBucket(capacity=100, refill_rate=10)  # 10 tokens/second
        bucket.consume(50)  # 50 remaining
        
        time.sleep(1.0)  # Wait 1 second
        bucket._refill()
        
        # Should have ~60 tokens (50 + 10*1)
        assert bucket.tokens >= 59  # Allow small timing variance
        assert bucket.tokens <= 61
    
    def test_refill_cap(self):
        """Refill doesn't exceed capacity"""
        bucket = TokenBucket(capacity=100, refill_rate=10)
        bucket.consume(10)  # 90 remaining
        
        time.sleep(5.0)  # Wait 5 seconds (would add 50 tokens)
        bucket._refill()
        
        assert bucket.tokens == 100  # Capped at capacity
    
    def test_time_until_available(self):
        """Calculate wait time correctly"""
        bucket = TokenBucket(capacity=100, refill_rate=10)
        bucket.consume(90)  # 10 remaining
        
        # Need 50 tokens, have 10, need 40 more at rate of 10/sec = 4 seconds
        wait_time = bucket.time_until_available(50)
        assert 3.9 <= wait_time <= 4.1  # Allow small variance
    
    def test_immediate_availability(self):
        """Returns 0 when tokens available"""
        bucket = TokenBucket(capacity=100, refill_rate=10)
        wait_time = bucket.time_until_available(50)
        assert wait_time == 0.0


class TestCostCalculator:
    """Test LLM cost calculation"""
    
    def test_openai_gpt4o_cost(self):
        """Calculate GPT-4o cost correctly"""
        cost = CostCalculator.calculate_cost(
            provider="openai",
            model="gpt-4o",
            input_tokens=1000,
            output_tokens=500
        )
        # Input: 1000 * $2.50/1M = $0.0025
        # Output: 500 * $10.00/1M = $0.0050
        # Total: $0.0075
        assert abs(cost - 0.0075) < 0.0001
    
    def test_anthropic_claude_cost(self):
        """Calculate Claude 3.5 Sonnet cost correctly"""
        cost = CostCalculator.calculate_cost(
            provider="anthropic",
            model="claude-3-5-sonnet-20241022",
            input_tokens=2000,
            output_tokens=1000
        )
        # Input: 2000 * $3.00/1M = $0.006
        # Output: 1000 * $15.00/1M = $0.015
        # Total: $0.021
        assert abs(cost - 0.021) < 0.0001
    
    def test_gemini_flash_cost(self):
        """Calculate Gemini Flash cost correctly"""
        cost = CostCalculator.calculate_cost(
            provider="google",
            model="gemini-2.5-flash",
            input_tokens=5000,
            output_tokens=2000
        )
        # Input: 5000 * $0.075/1M = $0.000375
        # Output: 2000 * $0.30/1M = $0.0006
        # Total: $0.000975
        assert abs(cost - 0.000975) < 0.0001
    
    def test_unknown_provider(self):
        """Returns 0 for unknown provider"""
        cost = CostCalculator.calculate_cost(
            provider="unknown",
            model="model-x",
            input_tokens=1000,
            output_tokens=500
        )
        assert cost == 0.0
    
    def test_unknown_model(self):
        """Returns 0 for unknown model"""
        cost = CostCalculator.calculate_cost(
            provider="openai",
            model="gpt-unknown",
            input_tokens=1000,
            output_tokens=500
        )
        assert cost == 0.0
    
    def test_model_name_fuzzy_match(self):
        """Matches similar model names"""
        # Test with partial model name
        cost = CostCalculator.calculate_cost(
            provider="openai",
            model="gpt-4o-2024-05-13",  # Contains "gpt-4o"
            input_tokens=1000,
            output_tokens=500
        )
        # Should match gpt-4o pricing
        assert abs(cost - 0.0075) < 0.0001
    
    def test_zero_tokens(self):
        """Handles zero tokens"""
        cost = CostCalculator.calculate_cost(
            provider="openai",
            model="gpt-4o",
            input_tokens=0,
            output_tokens=0
        )
        assert cost == 0.0


class TestLLMMonitoringService:
    """Test LLM monitoring service"""
    
    def test_initialization(self):
        """Service initializes with default settings"""
        service = LLMMonitoringService()
        assert service.request_limiter is not None
        assert service.token_limiter is not None
        assert len(service.requests_history) == 0
        assert len(service.daily_costs) == 0
    
    def test_check_rate_limits_allowed(self):
        """Rate limit check passes when under limit"""
        service = LLMMonitoringService()
        result = service.check_rate_limits(estimated_tokens=1000)
        assert result["allowed"] is True
    
    def test_check_rate_limits_requests_exceeded(self):
        """Rate limit check fails when requests exceeded"""
        service = LLMMonitoringService()
        # Exhaust request bucket
        max_rpm = service.request_limiter.capacity
        for _ in range(max_rpm):
            service.request_limiter.consume(1)
        
        result = service.check_rate_limits(estimated_tokens=1000)
        assert result["allowed"] is False
        assert result["reason"] == "requests_per_minute"
        assert "retry_after" in result
    
    def test_check_rate_limits_tokens_exceeded(self):
        """Rate limit check fails when tokens exceeded"""
        service = LLMMonitoringService()
        # Exhaust token bucket
        max_tpm = service.token_limiter.capacity
        service.token_limiter.consume(max_tpm)
        
        result = service.check_rate_limits(estimated_tokens=1000)
        assert result["allowed"] is False
        assert result["reason"] == "tokens_per_minute"
        assert "retry_after" in result
    
    def test_track_usage(self):
        """Tracks usage and calculates cost"""
        service = LLMMonitoringService()
        
        result = service.track_usage(
            provider="openai",
            model="gpt-4o",
            input_tokens=1000,
            output_tokens=500,
            duration_seconds=1.5
        )
        
        assert result["provider"] == "openai"
        assert result["model"] == "gpt-4o"
        assert result["input_tokens"] == 1000
        assert result["output_tokens"] == 500
        assert result["total_tokens"] == 1500
        assert abs(result["cost_usd"] - 0.0075) < 0.0001
        assert result["duration_seconds"] == 1.5
        assert "timestamp" in result
        assert "daily_total_cost" in result
    
    def test_track_usage_accumulates_daily_cost(self):
        """Daily costs accumulate correctly"""
        service = LLMMonitoringService()
        
        # Make 3 requests
        for _ in range(3):
            service.track_usage(
                provider="openai",
                model="gpt-4o",
                input_tokens=1000,
                output_tokens=500,
                duration_seconds=1.0
            )
        
        # Get today's date
        from datetime import datetime
        today = datetime.now().date().isoformat()
        
        # Daily cost should be 3 * $0.0075 = $0.0225
        assert abs(service.daily_costs[today] - 0.0225) < 0.0001
    
    def test_track_usage_detects_over_request_limit(self):
        """Detects when single request exceeds limit"""
        service = LLMMonitoringService()
        service.max_cost_per_request = 0.001  # Set very low limit
        
        result = service.track_usage(
            provider="openai",
            model="gpt-4o",
            input_tokens=1000,
            output_tokens=500,
            duration_seconds=1.0
        )
        
        assert result["over_request_limit"] is True
        assert result["cost_usd"] > service.max_cost_per_request
    
    def test_track_usage_detects_over_daily_limit(self):
        """Detects when daily spending exceeds limit"""
        service = LLMMonitoringService()
        service.daily_spending_limit = 0.01  # Set low limit
        
        # Make enough requests to exceed daily limit
        for _ in range(5):
            result = service.track_usage(
                provider="openai",
                model="gpt-4o",
                input_tokens=1000,
                output_tokens=500,
                duration_seconds=1.0
            )
        
        # Last result should show over daily limit
        assert result["over_daily_limit"] is True
        assert result["daily_total_cost"] > service.daily_spending_limit
    
    def test_check_cost_limits_request_limit(self):
        """Check cost limits for single request"""
        service = LLMMonitoringService()
        service.max_cost_per_request = 0.01
        
        # Try to make expensive request
        result = service.check_cost_limits(estimated_cost=0.05)
        
        assert result["allowed"] is False
        assert result["reason"] == "max_cost_per_request"
        assert result["limit"] == 0.01
        assert result["estimated_cost"] == 0.05
    
    def test_check_cost_limits_daily_limit(self):
        """Check cost limits for daily spending"""
        service = LLMMonitoringService()
        service.daily_spending_limit = 0.10
        
        # Accumulate some daily spending
        from datetime import datetime
        today = datetime.now().date().isoformat()
        service.daily_costs[today] = 0.08
        
        # Try to add more
        result = service.check_cost_limits(estimated_cost=0.05)
        
        assert result["allowed"] is False
        assert result["reason"] == "daily_spending_limit"
        assert result["limit"] == 0.10
        assert result["daily_total"] == 0.08
        assert result["estimated_cost"] == 0.05
    
    def test_check_cost_limits_allowed(self):
        """Cost check passes when under limits"""
        service = LLMMonitoringService()
        result = service.check_cost_limits(estimated_cost=0.001)
        assert result["allowed"] is True
    
    def test_get_stats_empty(self):
        """Stats work with no history"""
        service = LLMMonitoringService()
        stats = service.get_stats()
        
        assert stats["total_requests"] == 0
        assert stats["total_tokens"] == 0
        assert stats["total_cost"] == 0.0
        assert stats["average_cost"] == 0.0
    
    def test_get_stats_with_history(self):
        """Stats calculate correctly with history"""
        service = LLMMonitoringService()
        
        # Add some history
        for _ in range(5):
            service.track_usage(
                provider="openai",
                model="gpt-4o",
                input_tokens=1000,
                output_tokens=500,
                duration_seconds=1.0
            )
        
        stats = service.get_stats()
        
        assert stats["total_requests"] == 5
        assert stats["total_tokens"] == 7500  # 1500 * 5
        assert abs(stats["total_cost"] - 0.0375) < 0.0001  # $0.0075 * 5
        assert abs(stats["average_cost"] - 0.0075) < 0.0001
        assert "recent_hour" in stats
        assert "daily_costs" in stats
        assert "rate_limits" in stats
    
    def test_request_history_maxlen(self):
        """Request history maintains maxlen"""
        service = LLMMonitoringService()
        
        # Add more than maxlen (1000) requests
        for _ in range(1200):
            service.track_usage(
                provider="openai",
                model="gpt-3.5-turbo",
                input_tokens=100,
                output_tokens=50,
                duration_seconds=0.5
            )
        
        # Should only keep last 1000
        assert len(service.requests_history) == 1000


class TestIntegrationScenarios:
    """Integration tests for real-world scenarios"""
    
    def test_burst_then_throttle(self):
        """Can handle burst, then throttles correctly"""
        service = LLMMonitoringService()
        
        # Make burst of requests
        for _ in range(10):
            result = service.check_rate_limits(estimated_tokens=1000)
            assert result["allowed"] is True
        
        # Eventually should throttle (depends on rate limits)
        throttled = False
        for _ in range(100):
            result = service.check_rate_limits(estimated_tokens=1000)
            if not result["allowed"]:
                throttled = True
                break
        
        assert throttled is True
    
    def test_track_multiple_providers(self):
        """Can track usage across multiple providers"""
        service = LLMMonitoringService()
        
        # Use different providers
        service.track_usage("openai", "gpt-4o", 1000, 500, 1.0)
        service.track_usage("anthropic", "claude-3-5-sonnet-20241022", 2000, 1000, 1.5)
        service.track_usage("google", "gemini-2.5-flash", 5000, 2000, 0.8)
        
        stats = service.get_stats()
        assert stats["total_requests"] == 3
        
        # Check costs accumulated correctly
        # OpenAI: $0.0075, Anthropic: $0.021, Google: $0.000975
        expected_total = 0.0075 + 0.021 + 0.000975
        assert abs(stats["total_cost"] - expected_total) < 0.0001
    
    def test_daily_spending_resets(self):
        """Daily spending tracked separately per day"""
        service = LLMMonitoringService()
        from datetime import datetime
        
        # Track today
        today = datetime.now().date().isoformat()
        service.track_usage("openai", "gpt-4o", 1000, 500, 1.0)
        
        # Manually add yesterday's cost
        yesterday = "2025-10-23"
        service.daily_costs[yesterday] = 0.05
        
        # Today and yesterday should be separate
        assert today in service.daily_costs
        assert yesterday in service.daily_costs
        assert service.daily_costs[today] != service.daily_costs[yesterday]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
