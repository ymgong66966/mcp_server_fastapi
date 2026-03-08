"""
Firecrawl Rate Limit Discovery Test

Ramps up requests per minute until we hit 429 (rate limited).
Tests each endpoint (/scrape, /map, /search) independently.

Usage:
    export FIRECRAWL_API_KEY=fc-your-key
    python load_tests/test_rate_limits.py
"""

import asyncio
import os
import time
import json
import httpx
from dataclasses import dataclass, field
from typing import List

API_KEY = os.getenv("FIRECRAWL_API_KEY", "")
BASE_URL = "https://api.firecrawl.dev"

# Simple test targets
TEST_URL_SCRAPE = "https://example.com"
TEST_URL_MAP = "https://firecrawl.dev"
TEST_QUERY_SEARCH = "what is respite care"


@dataclass
class TestResult:
    endpoint: str
    total_sent: int = 0
    success: int = 0
    rate_limited: int = 0
    errors: int = 0
    first_429_at: int = 0
    latencies_ms: List[float] = field(default_factory=list)
    elapsed_seconds: float = 0.0


async def call_scrape(client: httpx.AsyncClient) -> tuple:
    """Call /v1/scrape. Returns (status_code, latency_ms)."""
    start = time.monotonic()
    try:
        resp = await client.post(
            f"{BASE_URL}/v1/scrape",
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={"url": TEST_URL_SCRAPE, "formats": ["markdown"], "onlyMainContent": True},
            timeout=30.0,
        )
        latency = (time.monotonic() - start) * 1000
        return resp.status_code, latency
    except Exception as e:
        latency = (time.monotonic() - start) * 1000
        return -1, latency


async def call_map(client: httpx.AsyncClient) -> tuple:
    """Call /v2/map. Returns (status_code, latency_ms)."""
    start = time.monotonic()
    try:
        resp = await client.post(
            f"{BASE_URL}/v2/map",
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={"url": TEST_URL_MAP, "search": "pricing", "limit": 3},
            timeout=30.0,
        )
        latency = (time.monotonic() - start) * 1000
        return resp.status_code, latency
    except Exception as e:
        latency = (time.monotonic() - start) * 1000
        return -1, latency


async def call_search(client: httpx.AsyncClient) -> tuple:
    """Call /v1/search. Returns (status_code, latency_ms)."""
    start = time.monotonic()
    try:
        resp = await client.post(
            f"{BASE_URL}/v1/search",
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={"query": TEST_QUERY_SEARCH, "limit": 3},
            timeout=30.0,
        )
        latency = (time.monotonic() - start) * 1000
        return resp.status_code, latency
    except Exception as e:
        latency = (time.monotonic() - start) * 1000
        return -1, latency


async def ramp_test(
    name: str,
    call_fn,
    start_rpm: int = 5,
    max_rpm: int = 120,
    step: int = 5,
) -> TestResult:
    """Ramp up from start_rpm to max_rpm, stop when we hit 429."""
    result = TestResult(endpoint=name)
    print(f"\n{'='*60}")
    print(f"Rate Limit Test: {name}")
    print(f"Ramping from {start_rpm} to {max_rpm} RPM (step={step})")
    print(f"{'='*60}")

    async with httpx.AsyncClient() as client:
        for target_rpm in range(start_rpm, max_rpm + 1, step):
            interval = 60.0 / target_rpm  # seconds between requests
            batch_size = min(target_rpm, 20)  # send a batch, measure over ~1 min window
            batch_start = time.monotonic()

            successes = 0
            rate_limits = 0
            errors = 0
            latencies = []

            for i in range(batch_size):
                status, latency = await call_fn(client)
                result.total_sent += 1
                latencies.append(latency)

                if status == 200:
                    successes += 1
                    result.success += 1
                elif status == 429:
                    rate_limits += 1
                    result.rate_limited += 1
                    if result.first_429_at == 0:
                        result.first_429_at = result.total_sent
                else:
                    errors += 1
                    result.errors += 1

                # Pace to match target RPM
                if i < batch_size - 1:
                    await asyncio.sleep(interval)

            batch_elapsed = time.monotonic() - batch_start
            actual_rpm = batch_size / batch_elapsed * 60 if batch_elapsed > 0 else 0
            avg_latency = sum(latencies) / len(latencies) if latencies else 0
            result.latencies_ms.extend(latencies)

            status_str = f"OK={successes} 429={rate_limits} ERR={errors}"
            print(
                f"  Target RPM={target_rpm:>4} | Actual RPM={actual_rpm:>6.1f} | "
                f"Avg latency={avg_latency:>7.0f}ms | {status_str}"
            )

            if rate_limits > 0:
                print(f"\n  >>> HIT RATE LIMIT at ~{target_rpm} RPM (request #{result.first_429_at})")
                break

            # Brief cooldown between ramp steps
            await asyncio.sleep(2.0)

    result.elapsed_seconds = time.monotonic()
    return result


async def main():
    if not API_KEY:
        print("ERROR: Set FIRECRAWL_API_KEY environment variable")
        return

    print("Firecrawl Rate Limit Discovery Test")
    print(f"API Key: {API_KEY[:10]}...{API_KEY[-4:]}")
    print()

    results = []

    # Test /map first (cheapest endpoint)
    r = await ramp_test("/v2/map", call_map, start_rpm=5, max_rpm=120, step=10)
    results.append(r)
    await asyncio.sleep(5)  # cooldown between endpoints

    # Test /search
    r = await ramp_test("/v1/search", call_search, start_rpm=5, max_rpm=60, step=5)
    results.append(r)
    await asyncio.sleep(5)

    # Test /scrape (most expensive — use smaller ramp)
    r = await ramp_test("/v1/scrape", call_scrape, start_rpm=5, max_rpm=60, step=5)
    results.append(r)

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for r in results:
        avg_lat = sum(r.latencies_ms) / len(r.latencies_ms) if r.latencies_ms else 0
        p95_lat = sorted(r.latencies_ms)[int(len(r.latencies_ms) * 0.95)] if r.latencies_ms else 0
        limit_str = f"~{r.first_429_at} requests" if r.first_429_at else "NOT HIT"
        print(
            f"  {r.endpoint:>15}: "
            f"sent={r.total_sent} ok={r.success} 429={r.rate_limited} err={r.errors} | "
            f"avg={avg_lat:.0f}ms p95={p95_lat:.0f}ms | "
            f"Rate limit: {limit_str}"
        )


if __name__ == "__main__":
    asyncio.run(main())
