# Firecrawl Load Tests

Tests to understand Firecrawl API rate limits, latency, and concurrent user capacity.

## Firecrawl Rate Limits (from docs)

| Plan | /scrape RPM | /map RPM | /search RPM |
|------|-------------|----------|-------------|
| Free | 10 | 10 | 5 |
| Hobby | 100 | 100 | 50 |
| Standard | 500 | 500 | 250 |
| Growth | 5,000 | 5,000 | 2,500 |

## Scripts

| Script | Purpose |
|--------|---------|
| `test_rate_limits.py` | Find actual rate limits by ramping up requests until 429 |
| `test_latency.py` | Measure per-call latency for scrape, map, and search |
| `test_concurrent_users.py` | Simulate N concurrent deep_search sessions |

## Usage

```bash
# Set your API key
export FIRECRAWL_API_KEY=fc-your-key-here

# Run individual tests
python load_tests/test_rate_limits.py
python load_tests/test_latency.py
python load_tests/test_concurrent_users.py --users 5
```
