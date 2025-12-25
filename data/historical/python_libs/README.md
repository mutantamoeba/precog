# Python Sports Library Caches

This document describes external cache locations used by Python sports data libraries.
These libraries manage their own caching mechanisms - we document them here for reference.

## Libraries and Cache Locations

### 1. pybaseball

**Description:** MLB statistics from Statcast, Baseball Reference, FanGraphs

**Cache Location:** `~/.pybaseball/cache/`

**Data Coverage:**
- Statcast data: 2015-present (pitch-level tracking)
- Baseball Reference: 1876-present (historical stats)
- FanGraphs: 2002-present (advanced metrics)

**Example Usage:**
```python
from pybaseball import statcast, batting_stats

# Automatically cached on first call
data = statcast("2023-04-01", "2023-04-30")
batting = batting_stats(2023)
```

**Cache Management:**
```python
from pybaseball import cache

# Check cache status
cache.enable()  # Enable caching
cache.purge()   # Clear cache
```

### 2. nfl_data_py

**Description:** NFL play-by-play, roster, schedule data from nflverse

**Cache Location:** Auto-managed (in-memory caching, downloads from nflverse)

**Data Coverage:**
- Play-by-play: 1999-present
- Rosters: 1999-present
- Schedules: 1999-present
- Draft picks: 1980-present

**Example Usage:**
```python
import nfl_data_py as nfl

# Data is downloaded from nflverse GitHub
pbp = nfl.import_pbp_data([2023])
rosters = nfl.import_rosters([2023])
schedule = nfl.import_schedules([2023])
```

**Data Source:** https://github.com/nflverse/nflverse-data

### 3. nflreadpy

**Description:** NFL advanced stats and next-gen metrics

**Cache Location:** Auto-managed (follows nflverse structure)

**Data Coverage:**
- Next-Gen Stats: 2016-present
- Advanced passing: 2016-present
- Expected points: 1999-present

**Example Usage:**
```python
import nflreadpy as nflr

# Fetches from nflverse with local caching
ngs_passing = nflr.load_nextgen_stats(2023, stat_type="passing")
ngs_rushing = nflr.load_nextgen_stats(2023, stat_type="rushing")
```

### 4. nba_api

**Description:** Official NBA statistics from stats.nba.com

**Cache Location:** `~/.nba_api/` (when using custom caching)

**Data Coverage:**
- Game logs: 1946-present
- Player stats: 1996-present (detailed)
- Shot charts: 1996-present

**Rate Limiting:** ~60 requests/minute (throttled by NBA API)

**Example Usage:**
```python
from nba_api.stats.endpoints import leaguegamefinder
from nba_api.stats.static import teams

# Get team info
nba_teams = teams.get_teams()

# Get game logs (respects rate limits)
gamefinder = leaguegamefinder.LeagueGameFinder(
    team_id_nullable="1610612744",  # Warriors
    season_nullable="2023-24"
)
games = gamefinder.get_data_frames()[0]
```

**Custom Caching:**
```python
import json
from pathlib import Path

# Implement custom caching for repeated calls
cache_dir = Path.home() / ".nba_api"
cache_dir.mkdir(exist_ok=True)

def cached_api_call(endpoint, params, cache_file):
    cache_path = cache_dir / cache_file
    if cache_path.exists():
        return json.loads(cache_path.read_text())
    result = endpoint(**params).get_dict()
    cache_path.write_text(json.dumps(result))
    return result
```

## Clearing External Caches

If you need to refresh data from these libraries:

```bash
# Clear pybaseball cache
rm -rf ~/.pybaseball/cache/

# Clear nba_api cache (if using custom caching)
rm -rf ~/.nba_api/

# nfl_data_py and nflreadpy re-download on each run
# No persistent cache to clear
```

## Integration with Precog

Use the `seed-lib` CLI command to seed from these libraries:

```bash
# Seed MLB data from pybaseball
python main.py data seed-lib --source pybaseball --seasons 2023,2024

# Seed NFL data from nfl_data_py
python main.py data seed-lib --source nfl_data_py --seasons 2023,2024

# Seed NBA data from nba_api
python main.py data seed-lib --source nba_api --seasons 2023,2024
```

## Related Documentation

- `data/historical/README.md` - Main cache documentation
- `src/precog/database/seeding/cache_config.py` - Unified cache configuration
- `src/precog/database/seeding/sources/` - Library adapters
