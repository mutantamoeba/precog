# Historical Elo Data

This directory contains historical Elo ratings data for sports teams.

## Data Source: FiveThirtyEight NFL Elo

The NFL Elo dataset contains game-by-game Elo ratings from 1920 to 2020.

### Download Instructions

```bash
# Download from FiveThirtyEight's nfl-elo-game repository
curl -L "https://raw.githubusercontent.com/fivethirtyeight/nfl-elo-game/master/data/nfl_games.csv" -o data/historical/nfl_elo.csv
```

### Data Format

| Column | Description |
|--------|-------------|
| date | Game date (YYYY-MM-DD) |
| season | Season year |
| neutral | 1 if neutral site, 0 otherwise |
| playoff | 1 if playoff game, 0 if regular season |
| team1 | Team 1 code (e.g., KC, BUF) |
| team2 | Team 2 code |
| elo1 | Team 1 pre-game Elo rating |
| elo2 | Team 2 pre-game Elo rating |
| elo_prob1 | Team 1 win probability |
| score1 | Team 1 final score |
| score2 | Team 2 final score |
| result1 | 1 if team1 won, 0 otherwise |

### Coverage

- **Seasons**: 1920 - 2020 (101 seasons)
- **Records**: ~16,810 games (33,620 team-game records)
- **Teams**: 123 unique team codes (includes defunct franchises)

### Loading Data

Use the historical Elo loader to parse and seed the database:

```python
from pathlib import Path
from precog.database.seeding.historical_elo_loader import (
    parse_fivethirtyeight_csv,
    load_fivethirtyeight_elo,
)

# Parse specific seasons
records = list(parse_fivethirtyeight_csv(
    Path("data/historical/nfl_elo.csv"),
    seasons=[2018, 2019, 2020]
))

# Or load directly into database
result = load_fivethirtyeight_elo(
    Path("data/historical/nfl_elo.csv"),
    seasons=[2018, 2019, 2020]
)
print(f"Loaded {result.records_inserted} records")
```

### Data Availability Note

FiveThirtyEight's live NFL Elo API (`projects.fivethirtyeight.com/nfl-api/`) was
deprecated in late 2023. This archived dataset from their GitHub repository
contains data through the 2020 season. For more recent data, consider:

- [nfeloqb](https://github.com/greerreNFL/nfeloqb) - Community-maintained QB Elo model
- [nfelo](https://github.com/greerreNFL/nfelo) - Community-maintained team Elo rankings

## License

FiveThirtyEight data is available under Creative Commons Attribution 4.0 license.
See: https://github.com/fivethirtyeight/data
