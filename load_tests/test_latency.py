"""
Firecrawl Latency Profiling Test

Measures per-call latency for each endpoint with realistic payloads
matching what deep_search actually sends.

Usage:
    export FIRECRAWL_API_KEY=fc-your-key
    python load_tests/test_latency.py
"""

import asyncio
import os
import time
import statistics
import httpx

API_KEY = os.getenv("FIRECRAWL_API_KEY", "")
BASE_URL = "https://api.firecrawl.dev"

# Realistic payloads matching actual deep_search usage
SCRAPE_URLS = [
    "https://www.comfortkeepers.com/offices/illinois/chicago",
    "https://homecareforpatients.com/",
    "https://www.caring.com/senior-living/illinois/chicago",
]

MAP_TARGETS = [
    {"url": "https://www.hcpcaregivers.com", "queries": ["Mandarin speaking caregivers", "pricing rates"]},
    {"url": "https://www.comfortkeepers.com", "queries": ["in-home care services", "pricing"]},
]

SEARCH_QUERIES = [
    "in-home caregiver agency South Loop Chicago Mandarin speaking",
    "adult daycare memory care Lincoln Park Chicago",
    "Medicaid home care services Illinois",
]

SAMPLES = 5  # Number of calls per endpoint
DELAY_BETWEEN = 3.0  # Seconds between calls (stay well under rate limits)


async def measure_scrape(client: httpx.AsyncClient, url: str) -> dict:
    start = time.monotonic()
    try:
        resp = await client.post(
            f"{BASE_URL}/v1/scrape",
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={
                "url": url,
                "formats": ["json"],
                "jsonOptions": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "queries": {"type": "string"},
                            "answer": {"type": "string"},
                        },
                    },
                    "prompt": "queries: What services do they offer?\nanswer: answer from the website",
                },
                "onlyMainContent": True,
                "timeout": 30000,
            },
            timeout=60.0,
        )
        latency = (time.monotonic() - start) * 1000
        body_size = len(resp.content)
        return {"status": resp.status_code, "latency_ms": latency, "body_bytes": body_size}
    except Exception as e:
        latency = (time.monotonic() - start) * 1000
        return {"status": -1, "latency_ms": latency, "error": str(e)}


async def measure_map(client: httpx.AsyncClient, url: str, search: str) -> dict:
    start = time.monotonic()
    try:
        resp = await client.post(
            f"{BASE_URL}/v2/map",
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={"url": url, "search": search, "limit": 3, "sitemap": "include"},
            timeout=30.0,
        )
        latency = (time.monotonic() - start) * 1000
        body_size = len(resp.content)
        return {"status": resp.status_code, "latency_ms": latency, "body_bytes": body_size}
    except Exception as e:
        latency = (time.monotonic() - start) * 1000
        return {"status": -1, "latency_ms": latency, "error": str(e)}


async def measure_search(client: httpx.AsyncClient, query: str) -> dict:
    start = time.monotonic()
    try:
        resp = await client.post(
            f"{BASE_URL}/v1/search",
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={"query": query, "limit": 3},
            timeout=30.0,
        )
        latency = (time.monotonic() - start) * 1000
        body_size = len(resp.content)
        return {"status": resp.status_code, "latency_ms": latency, "body_bytes": body_size}
    except Exception as e:
        latency = (time.monotonic() - start) * 1000
        return {"status": -1, "latency_ms": latency, "error": str(e)}


def print_stats(name: str, results: list):
    latencies = [r["latency_ms"] for r in results if r["status"] == 200]
    errors = [r for r in results if r["status"] != 200]

    if not latencies:
        print(f"  {name}: ALL FAILED ({len(errors)} errors)")
        for e in errors[:3]:
            print(f"    - status={e['status']} {e.get('error', '')[:80]}")
        return

    avg = statistics.mean(latencies)
    med = statistics.median(latencies)
    mn = min(latencies)
    mx = max(latencies)
    p95 = sorted(latencies)[int(len(latencies) * 0.95)] if len(latencies) > 1 else mx
    avg_bytes = statistics.mean([r["body_bytes"] for r in results if r["status"] == 200])

    print(f"  {name}:")
    print(f"    Samples: {len(latencies)} ok, {len(errors)} failed")
    print(f"    Latency: avg={avg:.0f}ms  median={med:.0f}ms  min={mn:.0f}ms  max={mx:.0f}ms  p95={p95:.0f}ms")
    print(f"    Avg response size: {avg_bytes:.0f} bytes")
    if errors:
        print(f"    Errors: {[e.get('status') for e in errors]}")


async def main():
    if not API_KEY:
        print("ERROR: Set FIRECRAWL_API_KEY environment variable")
        return

    print("Firecrawl Latency Profiling Test")
    print(f"API Key: {API_KEY[:10]}...{API_KEY[-4:]}")
    print(f"Samples per endpoint: {SAMPLES}")
    print(f"Delay between calls: {DELAY_BETWEEN}s")
    print()

    async with httpx.AsyncClient() as client:
        # --- /v2/map ---
        print("Testing /v2/map ...")
        map_results = []
        for i in range(SAMPLES):
            target = MAP_TARGETS[i % len(MAP_TARGETS)]
            query = target["queries"][i % len(target["queries"])]
            r = await measure_map(client, target["url"], query)
            map_results.append(r)
            print(f"  [{i+1}/{SAMPLES}] status={r['status']} latency={r['latency_ms']:.0f}ms")
            if i < SAMPLES - 1:
                await asyncio.sleep(DELAY_BETWEEN)

        await asyncio.sleep(3)

        # --- /v1/search ---
        print("\nTesting /v1/search ...")
        search_results = []
        for i in range(SAMPLES):
            query = SEARCH_QUERIES[i % len(SEARCH_QUERIES)]
            r = await measure_search(client, query)
            search_results.append(r)
            print(f"  [{i+1}/{SAMPLES}] status={r['status']} latency={r['latency_ms']:.0f}ms")
            if i < SAMPLES - 1:
                await asyncio.sleep(DELAY_BETWEEN)

        await asyncio.sleep(3)

        # --- /v1/scrape ---
        print("\nTesting /v1/scrape ...")
        scrape_results = []
        for i in range(SAMPLES):
            url = SCRAPE_URLS[i % len(SCRAPE_URLS)]
            r = await measure_scrape(client, url)
            scrape_results.append(r)
            print(f"  [{i+1}/{SAMPLES}] status={r['status']} latency={r['latency_ms']:.0f}ms")
            if i < SAMPLES - 1:
                await asyncio.sleep(DELAY_BETWEEN)

    # Summary
    print(f"\n{'='*60}")
    print("LATENCY SUMMARY")
    print(f"{'='*60}")
    print_stats("/v2/map", map_results)
    print_stats("/v1/search", search_results)
    print_stats("/v1/scrape", scrape_results)

    # Capacity estimate
    print(f"\n{'='*60}")
    print("CAPACITY ESTIMATE (for deep_search)")
    print(f"{'='*60}")
    scrape_lats = [r["latency_ms"] for r in scrape_results if r["status"] == 200]
    map_lats = [r["latency_ms"] for r in map_results if r["status"] == 200]
    if scrape_lats and map_lats:
        # A typical deep_search session: 1 google_places + 1 map + 3 scrapes
        typical_session_ms = (
            statistics.mean(map_lats)  # 1 map call
            + 3 * statistics.mean(scrape_lats)  # 3 scrapes (sequential with 2s delays)
            + 2 * 2000  # 2 delays of 2s between scrapes
        )
        print(f"  Typical deep_search session: ~{typical_session_ms/1000:.1f}s")
        print(f"    (1 map @ {statistics.mean(map_lats):.0f}ms + "
              f"3 scrapes @ {statistics.mean(scrape_lats):.0f}ms + 4s delays)")

        # How many concurrent users can the API handle?
        # At Hobby plan: 100 RPM for scrape = ~1.67/sec
        # Each deep_search uses ~4 API calls over ~session_time
        for plan, scrape_rpm in [("Hobby", 100), ("Standard", 500), ("Growth", 5000)]:
            calls_per_session = 4  # 1 map + 3 scrapes
            max_sessions_per_min = scrape_rpm / calls_per_session
            print(f"  {plan} plan ({scrape_rpm} RPM): ~{max_sessions_per_min:.0f} deep_search sessions/min")


if __name__ == "__main__":
    asyncio.run(main())
