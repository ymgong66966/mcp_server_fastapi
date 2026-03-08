"""
Firecrawl Concurrent User Simulation

Simulates N users each running a deep_search session simultaneously.
Each session follows the real deep_search pattern:
  1. google_places_search (via Google Maps, not Firecrawl — skipped here)
  2. website_map (1 call)
  3. scrape_multiple_websites (3 URLs sequentially with 2s delays)

Measures: success rate, total latency per session, API errors, 429s.

Usage:
    export FIRECRAWL_API_KEY=fc-your-key
    python load_tests/test_concurrent_users.py --users 3
    python load_tests/test_concurrent_users.py --users 5
    python load_tests/test_concurrent_users.py --users 10
"""

import argparse
import asyncio
import os
import time
import statistics
import httpx
from dataclasses import dataclass, field
from typing import List

API_KEY = os.getenv("FIRECRAWL_API_KEY", "")
BASE_URL = "https://api.firecrawl.dev"

# Realistic test scenarios (different users searching different things)
SCENARIOS = [
    {
        "name": "Caregiver search Chicago",
        "map_url": "https://www.comfortkeepers.com",
        "map_query": "in-home care services Chicago",
        "scrape_urls": [
            "https://www.comfortkeepers.com/offices/illinois/chicago",
            "https://www.caring.com/senior-living/illinois/chicago",
            "https://example.com",
        ],
    },
    {
        "name": "Memory care Lincoln Park",
        "map_url": "https://www.aplaceformom.com",
        "map_query": "memory care Lincoln Park Chicago",
        "scrape_urls": [
            "https://www.aplaceformom.com",
            "https://www.seniorliving.org",
            "https://example.com",
        ],
    },
    {
        "name": "Adult daycare Dallas",
        "map_url": "https://www.caring.com",
        "map_query": "adult daycare Dallas Texas",
        "scrape_urls": [
            "https://www.caring.com/senior-living/texas/dallas",
            "https://example.com",
            "https://www.aplaceformom.com",
        ],
    },
    {
        "name": "Home health aide NYC",
        "map_url": "https://www.care.com",
        "map_query": "home health aide New York City",
        "scrape_urls": [
            "https://www.care.com",
            "https://example.com",
            "https://www.caring.com",
        ],
    },
    {
        "name": "Hospice care Los Angeles",
        "map_url": "https://www.vitas.com",
        "map_query": "hospice care Los Angeles",
        "scrape_urls": [
            "https://www.vitas.com",
            "https://example.com",
            "https://www.caring.com",
        ],
    },
]


@dataclass
class SessionResult:
    user_id: int
    scenario: str
    total_ms: float = 0
    map_ms: float = 0
    scrape_ms: List[float] = field(default_factory=list)
    map_status: int = 0
    scrape_statuses: List[int] = field(default_factory=list)
    rate_limited: int = 0
    errors: int = 0
    success: bool = False


async def run_session(user_id: int, scenario: dict, client: httpx.AsyncClient) -> SessionResult:
    """Simulate one user's deep_search session."""
    result = SessionResult(user_id=user_id, scenario=scenario["name"])
    session_start = time.monotonic()

    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

    # Step 1: website_map
    start = time.monotonic()
    try:
        resp = await client.post(
            f"{BASE_URL}/v2/map",
            headers=headers,
            json={"url": scenario["map_url"], "search": scenario["map_query"], "limit": 3},
            timeout=30.0,
        )
        result.map_ms = (time.monotonic() - start) * 1000
        result.map_status = resp.status_code
        if resp.status_code == 429:
            result.rate_limited += 1
        elif resp.status_code != 200:
            result.errors += 1
    except Exception as e:
        result.map_ms = (time.monotonic() - start) * 1000
        result.map_status = -1
        result.errors += 1

    # Step 2: scrape 3 URLs sequentially with 2s delays
    for i, url in enumerate(scenario["scrape_urls"][:3]):
        if i > 0:
            await asyncio.sleep(2.0)

        start = time.monotonic()
        try:
            resp = await client.post(
                f"{BASE_URL}/v1/scrape",
                headers=headers,
                json={
                    "url": url,
                    "formats": ["markdown"],
                    "onlyMainContent": True,
                    "timeout": 30000,
                },
                timeout=60.0,
            )
            latency = (time.monotonic() - start) * 1000
            result.scrape_ms.append(latency)
            result.scrape_statuses.append(resp.status_code)
            if resp.status_code == 429:
                result.rate_limited += 1
            elif resp.status_code != 200:
                result.errors += 1
        except Exception as e:
            latency = (time.monotonic() - start) * 1000
            result.scrape_ms.append(latency)
            result.scrape_statuses.append(-1)
            result.errors += 1

    result.total_ms = (time.monotonic() - session_start) * 1000
    result.success = result.rate_limited == 0 and result.errors == 0
    return result


async def main():
    parser = argparse.ArgumentParser(description="Simulate concurrent deep_search users")
    parser.add_argument("--users", type=int, default=3, help="Number of concurrent users (default: 3)")
    parser.add_argument("--stagger", type=float, default=0.5, help="Seconds between user starts (default: 0.5)")
    args = parser.parse_args()

    if not API_KEY:
        print("ERROR: Set FIRECRAWL_API_KEY environment variable")
        return

    n_users = args.users
    stagger = args.stagger

    print(f"Firecrawl Concurrent User Simulation")
    print(f"API Key: {API_KEY[:10]}...{API_KEY[-4:]}")
    print(f"Users: {n_users}")
    print(f"Stagger: {stagger}s between user starts")
    print(f"Each user: 1 map + 3 scrapes (sequential with 2s delays)")
    print(f"Expected API calls: {n_users * 4} total ({n_users} map + {n_users * 3} scrape)")
    print()

    async with httpx.AsyncClient() as client:
        # Launch users with stagger
        tasks = []
        for i in range(n_users):
            scenario = SCENARIOS[i % len(SCENARIOS)]
            task = asyncio.create_task(run_session(i, scenario, client))
            tasks.append(task)
            if i < n_users - 1:
                await asyncio.sleep(stagger)

        results = await asyncio.gather(*tasks)

    # Results
    print(f"\n{'='*70}")
    print("PER-USER RESULTS")
    print(f"{'='*70}")
    for r in results:
        scrape_avg = statistics.mean(r.scrape_ms) if r.scrape_ms else 0
        status_icon = "OK" if r.success else "FAIL"
        rate_str = f" (429x{r.rate_limited})" if r.rate_limited else ""
        err_str = f" (err={r.errors})" if r.errors else ""
        print(
            f"  User {r.user_id:>2} [{status_icon}] {r.scenario:>30}: "
            f"total={r.total_ms/1000:.1f}s  "
            f"map={r.map_ms:.0f}ms({r.map_status})  "
            f"scrape_avg={scrape_avg:.0f}ms{rate_str}{err_str}"
        )

    # Aggregate
    print(f"\n{'='*70}")
    print("AGGREGATE")
    print(f"{'='*70}")
    total_sessions = len(results)
    ok_sessions = sum(1 for r in results if r.success)
    rate_limited = sum(r.rate_limited for r in results)
    total_errors = sum(r.errors for r in results)
    all_totals = [r.total_ms for r in results]
    all_scrapes = [ms for r in results for ms in r.scrape_ms]
    all_maps = [r.map_ms for r in results]

    print(f"  Sessions: {ok_sessions}/{total_sessions} succeeded")
    print(f"  Rate limited calls: {rate_limited}")
    print(f"  Error calls: {total_errors}")
    if all_totals:
        print(f"  Session duration: avg={statistics.mean(all_totals)/1000:.1f}s  "
              f"min={min(all_totals)/1000:.1f}s  max={max(all_totals)/1000:.1f}s")
    if all_maps:
        print(f"  Map latency: avg={statistics.mean(all_maps):.0f}ms  "
              f"min={min(all_maps):.0f}ms  max={max(all_maps):.0f}ms")
    if all_scrapes:
        print(f"  Scrape latency: avg={statistics.mean(all_scrapes):.0f}ms  "
              f"min={min(all_scrapes):.0f}ms  max={max(all_scrapes):.0f}ms")

    # Verdict
    print(f"\n{'='*70}")
    print("VERDICT")
    print(f"{'='*70}")
    if rate_limited == 0:
        print(f"  {n_users} concurrent users: NO RATE LIMITING detected")
        print(f"  Try increasing --users to find the limit")
    else:
        print(f"  {n_users} concurrent users: RATE LIMITED ({rate_limited} calls got 429)")
        print(f"  Reduce concurrent users or add longer delays between scrape calls")

    # Capacity projection
    if all_scrapes and rate_limited == 0:
        avg_session_s = statistics.mean(all_totals) / 1000
        calls_per_session = 4
        total_api_calls = n_users * calls_per_session
        test_duration_s = max(all_totals) / 1000
        actual_rpm = total_api_calls / test_duration_s * 60
        print(f"\n  Measured throughput: {actual_rpm:.0f} API calls/min across {n_users} users")
        print(f"  Average session time: {avg_session_s:.1f}s")


if __name__ == "__main__":
    asyncio.run(main())
