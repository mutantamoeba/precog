# Claude Code: Phase 0 Completion & Phase 1 Kickoff

## Context

You are working on **Precog**, an automated prediction market trading system. Phase 0 (documentation) is nearing completion. You need to:
1. Ensure all Phase 0 documents are consistent and up-to-date
2. Create missing documentation
3. Validate version control
4. Prepare for Phase 1 implementation

## Critical Project Information

**Project Structure:**
```
precog/
├── docs/
│   ├── foundation/          # Core architecture docs
│   ├── api-integration/     # API guides
│   ├── database/            # Schema and data design
│   ├── configuration/       # Config guides
│   └── development/         # Dev processes
├── config/                  # YAML configuration files
├── src/                     # Source code (create in Phase 1)
├── tests/                   # Test suite (create in Phase 1)
├── .env.template            # Environment variable template
└── requirements.txt         # Python dependencies
```

**Key Principles:**
- All prices use `Decimal`, never `float`
- Kalshi uses RSA-PSS authentication (NOT HMAC-SHA256)
- Database uses SCD Type 2 versioning (row_current_ind)
- Configuration: YAML files + DB overrides
- Test-driven development (>80% coverage)

**Recently Updated:**
- `API_INTEGRATION_GUIDE_V2.0.md` - Major corrections to Kalshi auth, expanded ESPN/Weather APIs
- All YAML config files should be reviewed against this

---

## TASK 1: Document Consistency Review

### Step 1.1: Read Key Documents

Read these documents in order:

1. **API_INTEGRATION_GUIDE_V2.0.md** (just created - this is SOURCE OF TRUTH for API info)
2. **MASTER_REQUIREMENTS_V2.1.md** (or latest version in docs/foundation/)
3. **ARCHITECTURE_DECISIONS_V2.1.md** (or latest in docs/foundation/)
4. **DATABASE_SCHEMA_SUMMARY_V1.1.md** (or latest in docs/database/)
5. **PROJECT_OVERVIEW_V1.2.md** (or latest in docs/foundation/)
6. All YAML files in `config/` directory

### Step 1.2: Check for Inconsistencies

Create a markdown summary (`CONSISTENCY_REVIEW.md`) with these sections:

#### A. API Authentication Discrepancies
- [ ] Do any docs still reference HMAC-SHA256 for Kalshi? (Should be RSA-PSS)
- [ ] Are API endpoints current?
- [ ] Are rate limits documented correctly?

#### B. Technology Stack Alignment
- [ ] Does MASTER_REQUIREMENTS list correct Python packages?
- [ ] Are versions specified in requirements.txt?
- [ ] Does PROJECT_OVERVIEW show correct tech stack?

#### C. Database Schema Consistency
- [ ] Does DATABASE_SCHEMA_SUMMARY match tables described in other docs?
- [ ] Are all price fields specified as DECIMAL(10,4)?
- [ ] Is SCD Type 2 (row_current_ind) consistently described?

#### D. Configuration System
- [ ] Do YAML files in config/ match what's described in docs?
- [ ] Are all config categories from YAML referenced in docs?
- [ ] Are environment variables (.env.template) complete?

#### E. Phase Definitions
- [ ] Are Phase 0 deliverables clearly marked as complete?
- [ ] Are Phase 1 tasks clearly defined?
- [ ] Do all phase descriptions match across documents?

#### F. Version Control
- [ ] Does each document have proper version header?
- [ ] Does filename match version in document?
- [ ] Is changelog present and current?

### Step 1.3: Provide Recommendations

For each inconsistency found, provide:
```markdown
**Issue:** [Description]
**Location:** [Document name, section]
**Current State:** [What it says now]
**Should Be:** [What it should say]
**Priority:** Critical / High / Medium / Low
**Affects:** [Which other documents/code]
```

---

## TASK 2: Make Recommended Updates

### Version Control Guidelines

**Version Format:** `DOCUMENTNAME_V#.#.md`

**Version Increments:**
- Major version (+1.0): Significant restructuring, major corrections
- Minor version (+0.1): Updates, additions, clarifications

**Current Versions (check docs for actual latest):**
- PROJECT_OVERVIEW_V1.2.md
- MASTER_REQUIREMENTS_V2.1.md
- ARCHITECTURE_DECISIONS_V2.1.md
- DATABASE_SCHEMA_SUMMARY_V1.1.md
- API_INTEGRATION_GUIDE_V2.0.md (just created)

**When Updating:**
1. Determine if change warrants version bump
2. Update version in document header
3. Update filename to match
4. Add changelog entry
5. Update MASTER_INDEX with new version

### Update Process

For each recommended update:

1. **Open the document**
2. **Make changes** following the recommendations
3. **Update version** if warranted:
   - Major corrections → +1.0
   - Minor updates → +0.1
   - Typos/formatting only → no version change
4. **Update changelog** at bottom of document
5. **Rename file** if version changed
6. **Log changes** in a `UPDATES_LOG.md` file

### Critical Updates to Make

Based on API_INTEGRATION_GUIDE_V2.0, ensure:

✅ **All documents reflect:**
- Kalshi uses RSA-PSS (not HMAC)
- OpenWeatherMap for weather data
- ESPN as primary game data source
- Balldontlie as backup
- Decimal pricing throughout
- Rate limiting strategies

---

## TASK 3: Filename-Version Consistency

### Check All Documents

For every `.md` file in `docs/`:

1. Open the file
2. Find the version in the header (look for `**Version:** X.Y`)
3. Extract the base name (e.g., PROJECT_OVERVIEW)
4. Check if filename matches: `BASENAME_VX.Y.md`
5. If mismatch, rename file to match version

### Create Report

Create `FILENAME_VERSION_REPORT.md`:

```markdown
# Filename-Version Consistency Report

## ✅ Correct Filenames
- PROJECT_OVERVIEW_V1.2.md (version 1.2)
- [List all correct ones]

## ❌ Mismatched Filenames
- **File:** old_name.md
- **Version in doc:** 2.1
- **Should be:** DOCUMENT_NAME_V2.1.md
- **Action:** Renamed ✅

## 📝 Documents Without Versions
- [Any docs missing version headers]
- **Action:** Add version headers or determine if needed
```

---

## TASK 4: Create Developer Onboarding Guide

### File Location
`docs/development/DEVELOPER_ONBOARDING_V1.0.md`

### Content Structure

```markdown
# Developer Onboarding Guide

**Version:** 1.0
**Last Updated:** [Today's date]
**Status:** ✅ Current
**Purpose:** Step-by-step guide for new developers joining the Precog project
**Audience:** Developers with basic Python knowledge, learning probability/trading

---

## Welcome to Precog!

This guide will help you get set up and contributing to Precog, an automated prediction market trading system.

**What you'll learn:**
- System architecture and design
- Development environment setup
- Coding standards and patterns
- How to run tests
- How to contribute

**Prerequisites:**
- Python 3.12 knowledge (basic to intermediate)
- Git basics
- Interest in probability and trading (we'll teach you!)
- Laptop with macOS, Linux, or Windows+WSL

---

## 1. Understanding Precog

### What is Precog?

[Brief overview - 2-3 paragraphs explaining the system]

### System Architecture

[High-level diagram/description]

**Key Components:**
1. **API Connectors** - Fetch data from Kalshi, ESPN, Weather APIs
2. **Database** - PostgreSQL with versioned records
3. **Odds Calculator** - Compute true probabilities from game states
4. **Trading Engine** - Execute trades when edges detected
5. **Configuration** - YAML-based config with DB overrides

### Technology Stack

- **Language:** Python 3.12
- **Database:** PostgreSQL 14+
- **Key Libraries:**
  - `psycopg2` - Database
  - `requests` - API calls
  - `cryptography` - Kalshi authentication
  - `pytest` - Testing
  - `pyyaml` - Configuration
- **Development:** Git, pytest, black (formatting), mypy (type checking)

**Read More:**
- [PROJECT_OVERVIEW_V1.2.md](../foundation/PROJECT_OVERVIEW_V1.2.md)
- [MASTER_REQUIREMENTS_V2.1.md](../foundation/MASTER_REQUIREMENTS_V2.1.md)

---

## 2. Environment Setup

### 2.1 Install Prerequisites

**macOS:**
```bash
# Install Homebrew (if not already installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python 3.12
brew install python@3.12

# Install PostgreSQL
brew install postgresql@14
brew services start postgresql@14

# Install Git (usually pre-installed)
brew install git
```

**Linux (Ubuntu/Debian):**
```bash
# Update package list
sudo apt update

# Install Python 3.12
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt install python3.12 python3.12-venv python3.12-dev

# Install PostgreSQL
sudo apt install postgresql postgresql-contrib

# Install Git
sudo apt install git
```

**Windows:**
- Install Python 3.12 from python.org
- Install PostgreSQL from postgresql.org
- Install Git from git-scm.com
- Use WSL2 for best experience (optional but recommended)

### 2.2 Clone Repository

```bash
# Clone the repo
git clone [repository-url] precog
cd precog

# Create Python virtual environment
python3.12 -m venv venv

# Activate virtual environment
source venv/bin/activate  # macOS/Linux
# OR
venv\Scripts\activate  # Windows
```

### 2.3 Install Python Dependencies

```bash
# Upgrade pip
pip install --upgrade pip

# Install project dependencies
pip install -r requirements.txt

# Install development dependencies
pip install -r requirements-dev.txt  # If exists
```

### 2.4 Set Up Database

```bash
# Create database
createdb precog_dev

# Run schema creation (Phase 1+)
python main.py db-init

# Verify
psql precog_dev -c "\dt"  # Should show tables
```

### 2.5 Configure Environment

```bash
# Copy environment template
cp .env.template .env

# Edit .env and add your credentials
nano .env  # or your preferred editor
```

**Required Environment Variables:**
```bash
# Kalshi Demo (get from https://demo.kalshi.co)
KALSHI_DEMO_KEY_ID=your_demo_key_id
KALSHI_DEMO_KEYFILE=/path/to/demo_private_key.pem

# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=precog_dev
DB_USER=postgres
DB_PASSWORD=your_password

# Weather API (get from https://openweathermap.org)
OPENWEATHER_API_KEY=your_api_key

# Optional: Balldontlie (https://balldontlie.io)
BALLDONTLIE_API_KEY=your_api_key
```

**Getting API Keys:**

1. **Kalshi Demo:**
   - Visit https://demo.kalshi.co/account/profile
   - Click "Create New API Key"
   - Download private key file immediately (can't retrieve later!)
   - Copy Key ID to .env

2. **OpenWeatherMap:**
   - Sign up at https://openweathermap.org/api
   - Free tier gives 1000 calls/day
   - API key appears in dashboard

3. **Balldontlie (Optional):**
   - Sign up at https://balldontlie.io
   - Free tier: 5 requests/minute
   - Used as backup to ESPN

### 2.6 Verify Setup

```bash
# Run health check (Phase 1+)
python main.py health-check

# Should output:
# ✅ Database connection: OK
# ✅ Kalshi API: Authenticated
# ✅ Environment variables: Complete
```

---

## 3. Project Structure

```
precog/
├── docs/                           # Documentation
│   ├── foundation/                 # Architecture, requirements
│   ├── api-integration/           # API guides
│   ├── database/                  # Schema docs
│   ├── configuration/             # Config guides
│   └── development/               # This file!
│
├── config/                        # YAML configuration
│   ├── database.yaml              # DB settings
│   ├── trading.yaml               # Trading params
│   ├── data_sources.yaml          # API configs
│   └── logging.yaml               # Logging setup
│
├── src/                           # Source code
│   ├── api_connectors/           # API clients
│   │   ├── kalshi_client.py
│   │   ├── espn_client.py
│   │   └── weather_client.py
│   ├── database/                 # Database layer
│   │   ├── connection.py
│   │   ├── models.py
│   │   └── crud_operations.py
│   ├── models/                   # Business logic
│   │   ├── odds_calculator.py
│   │   └── edge_detector.py
│   ├── trading/                  # Trading engine
│   │   └── order_executor.py
│   ├── utils/                    # Utilities
│   │   ├── config.py
│   │   ├── logger.py
│   │   └── decimal_helpers.py
│   └── main.py                   # CLI entry point
│
├── tests/                        # Test suite
│   ├── api_connectors/
│   ├── database/
│   ├── models/
│   └── integration/
│
├── .env                          # Environment vars (not in Git!)
├── .env.template                 # Template for .env
├── .gitignore
├── requirements.txt              # Dependencies
└── README.md
```

---

## 4. Development Workflow

### 4.1 Before Starting Work

```bash
# 1. Update from main
git checkout main
git pull origin main

# 2. Create feature branch
git checkout -b feature/your-feature-name

# 3. Activate virtual environment
source venv/bin/activate
```

### 4.2 While Working

```bash
# Run tests frequently
pytest

# Run specific test file
pytest tests/api_connectors/test_kalshi_client.py

# Check code formatting
black src/ tests/

# Check type hints
mypy src/
```

### 4.3 Before Committing

**Checklist:**
- [ ] All tests pass (`pytest`)
- [ ] Code formatted (`black .`)
- [ ] Type hints checked (`mypy src/`)
- [ ] No sensitive data in code (API keys, passwords)
- [ ] Docstrings added for new functions
- [ ] Changelog updated (if applicable)

```bash
# Add changes
git add .

# Commit with descriptive message
git commit -m "feat: Add Kalshi market fetching with pagination

- Implement get_markets() with cursor-based pagination
- Add Decimal price parsing
- Include rate limiting
- Tests: 15 new unit tests, all passing"

# Push to remote
git push origin feature/your-feature-name
```

### 4.4 Commit Message Format

Use conventional commits:

```
<type>: <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `test`: Adding tests
- `refactor`: Code refactoring
- `chore`: Maintenance tasks

**Example:**
```
feat: Add weather impact assessment for NFL games

- Implement OpenWeatherMap client
- Add stadium coordinates database
- Calculate weather impact on scoring
- Tests: 8 new tests for weather calculations

Closes #42
```

---

## 5. Coding Standards

### 5.1 Python Style

**Follow PEP 8:**
- 4 spaces for indentation (no tabs)
- Max line length: 100 characters
- Use `black` for automatic formatting

**Naming Conventions:**
```python
# Variables and functions: snake_case
user_name = "Alice"
def calculate_odds():
    pass

# Classes: PascalCase
class KalshiClient:
    pass

# Constants: UPPER_SNAKE_CASE
MAX_RETRIES = 3
API_BASE_URL = "https://api.example.com"

# Private methods: _leading_underscore
def _internal_helper():
    pass
```

### 5.2 Type Hints

**Always use type hints:**

```python
from typing import Dict, List, Optional
from decimal import Decimal

def calculate_edge(
    market_price: Decimal,
    true_probability: Decimal
) -> Decimal:
    """
    Calculate expected value edge.

    Args:
        market_price: Current market price (0.00-1.00)
        true_probability: Our calculated probability

    Returns:
        Edge percentage (positive = profitable)
    """
    return true_probability - market_price
```

### 5.3 Docstrings

**Every public function needs a docstring:**

```python
def fetch_live_games(sport: str) -> List[Dict]:
    """
    Fetch currently live games for a sport.

    Args:
        sport: Sport name ("nfl", "ncaaf", "nba")

    Returns:
        List of game dictionaries with scores and game state

    Raises:
        ValueError: If sport not supported
        APIError: If API request fails

    Example:
        >>> games = fetch_live_games("nfl")
        >>> for game in games:
        ...     print(f"{game['away_team']} @ {game['home_team']}")
    """
    # Implementation here
```

### 5.4 Critical Rules

**❌ NEVER do these:**

```python
# ❌ Don't use float for money
price = 0.65  # WRONG!

# ❌ Don't hardcode credentials
api_key = "secret_key_123"  # WRONG!

# ❌ Don't catch bare exceptions
try:
    do_something()
except:  # WRONG!
    pass
```

**✅ ALWAYS do these:**

```python
# ✅ Use Decimal for money
from decimal import Decimal
price = Decimal('0.65')

# ✅ Use environment variables
import os
api_key = os.getenv('API_KEY')

# ✅ Catch specific exceptions
try:
    do_something()
except ValueError as e:
    logger.error(f"Invalid value: {e}")
    raise
```

---

## 6. Testing

### 6.1 Test Structure

```
tests/
├── conftest.py              # Shared fixtures
├── api_connectors/
│   ├── test_kalshi_client.py
│   └── test_espn_client.py
├── database/
│   └── test_crud_operations.py
└── integration/
    └── test_full_pipeline.py
```

### 6.2 Writing Tests

**Use pytest:**

```python
# tests/models/test_odds_calculator.py

import pytest
from decimal import Decimal
from models.odds_calculator import calculate_implied_probability

class TestOddsCalculator:
    """Test suite for odds calculations."""

    def test_implied_probability_basic(self):
        """Test basic implied probability calculation."""
        # Given: Market price of 0.65
        market_price = Decimal('0.65')

        # When: Calculate implied probability
        prob = calculate_implied_probability(market_price)

        # Then: Should equal market price (no vig in this example)
        assert prob == market_price

    def test_implied_probability_invalid_input(self):
        """Test that invalid inputs raise ValueError."""
        with pytest.raises(ValueError):
            calculate_implied_probability(Decimal('1.5'))  # Over 1.0

        with pytest.raises(ValueError):
            calculate_implied_probability(Decimal('-0.1'))  # Negative

    @pytest.mark.parametrize("price,expected", [
        (Decimal('0.50'), Decimal('0.50')),
        (Decimal('0.25'), Decimal('0.25')),
        (Decimal('0.75'), Decimal('0.75')),
    ])
    def test_implied_probability_multiple_cases(self, price, expected):
        """Test multiple price points."""
        result = calculate_implied_probability(price)
        assert result == expected
```

### 6.3 Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/api_connectors/test_kalshi_client.py

# Run specific test
pytest tests/api_connectors/test_kalshi_client.py::TestKalshiClient::test_get_markets

# Run only fast tests (skip integration)
pytest -m "not integration"

# Run with coverage report
pytest --cov=src --cov-report=html
```

### 6.4 Test Coverage Requirements

**Minimum 80% coverage for all code.**

Check coverage:
```bash
pytest --cov=src --cov-report=term-missing

# View HTML report
open htmlcov/index.html
```

**Critical paths need 100% coverage:**
- Decimal price handling
- Kelly bet sizing
- Order execution
- Database transactions

---

## 7. Common Tasks

### 7.1 Adding a New API Endpoint

1. **Add method to API client:**
```python
# src/api_connectors/kalshi_client.py

def get_event(self, event_ticker: str) -> Dict:
    """Get single event by ticker."""
    response = self._make_request("GET", f"/events/{event_ticker}")
    return response.get("event", {})
```

2. **Add tests:**
```python
# tests/api_connectors/test_kalshi_client.py

def test_get_event(mock_client):
    """Test fetching single event."""
    mock_response = {"event": {"ticker": "TEST", "title": "Test Event"}}

    with patch.object(mock_client, '_make_request', return_value=mock_response):
        event = mock_client.get_event("TEST")
        assert event['ticker'] == "TEST"
```

3. **Update documentation:**
- Add endpoint to API_INTEGRATION_GUIDE
- Update changelog

### 7.2 Adding a Database Table

1. **Update schema in DATABASE_SCHEMA_SUMMARY.md**

2. **Create migration (Phase 2+):**
```sql
-- migrations/003_add_weather_table.sql

CREATE TABLE weather_conditions (
    id SERIAL PRIMARY KEY,
    game_id VARCHAR(100) NOT NULL,
    temperature_f DECIMAL(5,2),
    wind_mph DECIMAL(5,2),
    conditions VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (game_id) REFERENCES games(id)
);

CREATE INDEX idx_weather_game_id ON weather_conditions(game_id);
```

3. **Add ORM model:**
```python
# src/database/models.py

class WeatherCondition(Base):
    __tablename__ = 'weather_conditions'

    id = Column(Integer, primary_key=True)
    game_id = Column(String(100), ForeignKey('games.id'))
    temperature_f = Column(DECIMAL(5, 2))
    wind_mph = Column(DECIMAL(5, 2))
    conditions = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
```

### 7.3 Debugging Tips

**Enable debug logging:**
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

**Use Python debugger:**
```python
import pdb; pdb.set_trace()  # Breakpoint

# Or use ipdb for better interface
import ipdb; ipdb.set_trace()
```

**Check database contents:**
```bash
psql precog_dev

# List tables
\dt

# Query markets
SELECT ticker, yes_ask, volume FROM markets LIMIT 10;

# Check current records only
SELECT * FROM markets WHERE row_current_ind = TRUE;
```

---

## 8. Resources & Learning

### Documentation

**Project Docs:**
- [PROJECT_OVERVIEW](../foundation/PROJECT_OVERVIEW_V1.2.md) - System architecture
- [MASTER_REQUIREMENTS](../foundation/MASTER_REQUIREMENTS_V2.1.md) - Complete requirements
- [API_INTEGRATION_GUIDE](../api-integration/API_INTEGRATION_GUIDE_V2.0.md) - API details
- [DATABASE_SCHEMA](../database/DATABASE_SCHEMA_SUMMARY_V1.1.md) - Database design

**External Docs:**
- [Kalshi API](https://docs.kalshi.com) - Prediction market API
- [ESPN API Guide](https://gist.github.com/akeaswaran/b48b02f1c94f873c6655e7129910fc3b) - Hidden API
- [PostgreSQL](https://www.postgresql.org/docs/) - Database docs
- [pytest](https://docs.pytest.org/) - Testing framework

### Probability & Trading Concepts

**Key Concepts to Learn:**
- Expected Value (EV)
- Implied Probability
- Kelly Criterion
- Market Efficiency
- Arbitrage

**Recommended Reading:**
- "Thinking in Bets" by Annie Duke
- "The Signal and the Noise" by Nate Silver
- "Superforecasting" by Philip Tetlock
- [Kalshi Blog](https://kalshi.com/blog) - Prediction market insights

### Python Best Practices

- [PEP 8](https://pep8.org/) - Python style guide
- [Real Python](https://realpython.com/) - Tutorials
- [Python Type Hints](https://docs.python.org/3/library/typing.html)

---

## 9. Getting Help

### Internal Resources

1. **Check documentation first**
   - All docs are in `docs/` directory
   - Search for keywords in MASTER_INDEX

2. **Review test examples**
   - Tests show how code should be used
   - Look in `tests/` for examples

3. **Check Git history**
   - See how similar features were implemented
   - `git log --all --grep="keyword"`

### Communication

- **Questions:** Ask in team chat/Discord
- **Bugs:** Create GitHub issue with details
- **Features:** Propose in team discussion

### Troubleshooting Checklist

Problem? Check these:

- [ ] Is virtual environment activated? (`which python`)
- [ ] Are dependencies installed? (`pip list`)
- [ ] Are environment variables set? (`cat .env`)
- [ ] Is PostgreSQL running? (`pg_isready`)
- [ ] Are tests passing? (`pytest`)
- [ ] Is code formatted? (`black .`)

---

## 10. Next Steps

**You're ready to contribute!**

### Immediate Actions:

1. ✅ Complete environment setup (Section 2)
2. ✅ Run health check to verify
3. 📖 Read PROJECT_OVERVIEW for architecture understanding
4. 📖 Read API_INTEGRATION_GUIDE for Phase 1 context
5. 🧪 Run test suite (`pytest`) to see it work
6. 💻 Try making a small change and running tests

### Phase 1 Onboarding:

If starting Phase 1 implementation:

1. Read [PHASE_1_TASK_PLAN](PHASE_1_TASK_PLAN_V1.0.md)
2. Review Kalshi authentication section in API guide
3. Set up demo Kalshi account
4. Implement first task: Kalshi authentication
5. Write tests for your code
6. Submit PR when tests pass

### Learning Path:

**Week 1:** Setup + Architecture
- Complete setup
- Read core docs
- Understand system design

**Week 2:** APIs + Data
- Study API_INTEGRATION_GUIDE
- Understand Kalshi API
- Learn about game data sources

**Week 3:** Database + Testing
- Study DATABASE_SCHEMA
- Learn SCD Type 2 pattern
- Write your first tests

**Week 4:** Probability + Trading
- Learn EV calculations
- Understand Kelly Criterion
- Study odds modeling

---

## Appendix A: Glossary

**API**: Application Programming Interface - how we talk to external services
**Decimal**: Python type for exact decimal arithmetic (no floating point errors)
**Edge**: Positive expected value opportunity (market price < true probability)
**EV**: Expected Value - average profit per bet over many repetitions
**Kelly**: Kelly Criterion - optimal bet sizing formula
**Market**: Binary prediction market (YES or NO outcome)
**Odds**: Implied probability from market prices
**Position**: Open contract holdings in a market
**SCD Type 2**: Slowly Changing Dimension - method for versioning database records
**Series**: Group of related markets (e.g., all NFL games)
**Ticker**: Unique identifier for market/event/series

---

## Appendix B: Troubleshooting Common Issues

### "Import Error: No module named 'xxx'"

**Problem:** Missing Python package

**Solution:**
```bash
pip install -r requirements.txt
```

### "psycopg2 won't install"

**Problem:** Missing PostgreSQL development libraries

**Solution:**
```bash
# macOS
brew install postgresql

# Linux
sudo apt-get install libpq-dev python3-dev
```

### "Kalshi authentication failed"

**Problem:** Invalid credentials or incorrect auth method

**Solution:**
1. Verify API key in .env
2. Check private key file exists and is readable
3. Ensure using RSA-PSS (not HMAC!)
4. Test with demo environment first

### "Tests failing on Decimal precision"

**Problem:** Using float instead of Decimal

**Solution:**
```python
# ❌ Wrong
price = 0.65

# ✅ Correct
from decimal import Decimal
price = Decimal('0.65')
```

---

## Changelog

**v1.0 (2025-10-17):**
- Initial creation
- Complete setup instructions
- Coding standards
- Testing guidelines
- Common tasks and troubleshooting

---

**END OF DEVELOPER_ONBOARDING_V1.0.md**
```

Save this as: `docs/development/DEVELOPER_ONBOARDING_V1.0.md`

Customize sections as needed based on your team's specific needs!

---

## TASK 5: Review Master Index

### Step 5.1: Open Master Index

Read `docs/foundation/MASTER_INDEX_V2.1.md` (or latest version)

### Step 5.2: Verify Phase 0 Documents

Create a checklist (`PHASE_0_COMPLETENESS.md`):

```markdown
# Phase 0 Document Completeness Check

## Required Phase 0 Documents

### Foundation Documents
- [ ] PROJECT_OVERVIEW_V?.? - Exists, version matches filename
- [ ] MASTER_REQUIREMENTS_V?.? - Exists, version matches filename
- [ ] ARCHITECTURE_DECISIONS_V?.? - Exists, version matches filename
- [ ] MASTER_INDEX_V?.? - Exists, version matches filename
- [ ] GLOSSARY_V?.? - Exists, version matches filename
- [ ] DEVELOPMENT_PHASES_V?.? - Exists, version matches filename

### API & Integration
- [ ] API_INTEGRATION_GUIDE_V?.? - Exists, version matches filename
- [ ] KALSHI_DECIMAL_PRICING_CHEAT_SHEET_V?.? - Exists, version matches filename
- [ ] KALSHI_API_STRUCTURE_COMPREHENSIVE_V?.? - Exists (or marked archived)

### Database
- [ ] DATABASE_SCHEMA_SUMMARY_V?.? - Exists, version matches filename

### Configuration
- [ ] CONFIGURATION_GUIDE_V?.? - Exists, version matches filename

### Development
- [ ] DEVELOPER_ONBOARDING_V?.? - Exists (just created)
- [ ] PHASE_1_TASK_PLAN_V?.? - Exists, version matches filename

### YAML Files
- [ ] config/database.yaml - Exists and valid
- [ ] config/trading.yaml - Exists and valid
- [ ] config/data_sources.yaml - Exists and valid
- [ ] config/logging.yaml - Exists and valid

### Templates
- [ ] .env.template - Exists with all required variables

## Missing Documents

List any required docs that don't exist:
- [Document name]: [Why needed], [Priority]

## Version Mismatches in Index

List any documents where MASTER_INDEX has wrong version:
- [Document]: Index shows v?.?, actual file is v?.?

## Recommendations

1. [Action needed]
2. [Action needed]
```

### Step 5.3: Update Master Index

If any versions are wrong in MASTER_INDEX:
1. Update the version numbers
2. Update "Last Updated" date
3. Increment MASTER_INDEX version if many changes
4. Update changelog

---

## TASK 6: Prepare Git Commit

### Step 6.1: Review All Changes

```bash
git status
git diff
```

### Step 6.2: Stage Changes

```bash
# Stage all documentation updates
git add docs/

# Stage config files (if changed)
git add config/

# Stage templates (if changed)
git add .env.template

# Review what's staged
git status
```

### Step 6.3: Create Commit Message

```bash
git commit -m "docs: Complete Phase 0 documentation with consistency updates

Major Changes:
- Corrected Kalshi authentication across all docs (RSA-PSS, not HMAC)
- Updated API integration details for ESPN, Weather, Balldontlie
- Created DEVELOPER_ONBOARDING_V1.0.md with complete setup guide
- Synchronized all documents with API_INTEGRATION_GUIDE_V2.0
- Verified and corrected all filename-version mismatches
- Updated MASTER_INDEX with current versions

Document Updates:
- PROJECT_OVERVIEW: [describe changes if any]
- MASTER_REQUIREMENTS: [describe changes if any]
- ARCHITECTURE_DECISIONS: [describe changes if any]
- DATABASE_SCHEMA: [describe changes if any]
- MASTER_INDEX: Version updates for all Phase 0 docs

New Documents:
- DEVELOPER_ONBOARDING_V1.0.md
- CONSISTENCY_REVIEW.md (review notes)
- FILENAME_VERSION_REPORT.md (validation report)
- PHASE_0_COMPLETENESS.md (completeness check)

Phase 0 Status: ✅ COMPLETE
Ready for Phase 1: ✅ YES

All documents reviewed, consistent, and version-controlled.
API authentication corrected throughout.
Developer onboarding guide complete.
"
```

### Step 6.4: Push (if appropriate)

```bash
git push origin main
# OR if using feature branch:
git push origin phase-0-completion
```

---

## TASK 7: Phase 1 Kickoff

### Step 7.1: Read Phase 1 Plan

Read: `docs/development/PHASE_1_TASK_PLAN_V1.0.md`

### Step 7.2: Set Up Project Structure

Create the initial source code directories:

```bash
# Create directory structure
mkdir -p src/api_connectors
mkdir -p src/database
mkdir -p src/models
mkdir -p src/utils
mkdir -p tests/api_connectors
mkdir -p tests/database
mkdir -p tests/integration

# Create __init__.py files
touch src/__init__.py
touch src/api_connectors/__init__.py
touch src/database/__init__.py
touch src/models/__init__.py
touch src/utils/__init__.py
touch tests/__init__.py
```

### Step 7.3: Create requirements.txt

Based on REQUIREMENTS_AND_DEPENDENCIES document, create:

```
# requirements.txt

# Core
python-dotenv==1.0.0
pyyaml==6.0.1

# Database
psycopg2-binary==2.9.9
SQLAlchemy==2.0.23

# API Clients
requests==2.31.0
cryptography==41.0.7

# Utilities
structlog==23.2.0
click==8.1.7

# Testing
pytest==7.4.3
pytest-cov==4.1.0
pytest-mock==3.12.0

# Code Quality
black==23.11.0
mypy==1.7.1
```

### Step 7.4: Create .env.template

```bash
# .env.template

# ============================================
# KALSHI API CREDENTIALS
# ============================================
# Demo Environment (get from https://demo.kalshi.co)
KALSHI_DEMO_KEY_ID=your_demo_key_id_here
KALSHI_DEMO_KEYFILE=/path/to/demo_private_key.pem

# Production Environment (DO NOT USE until Phase 5+)
KALSHI_PROD_KEY_ID=your_prod_key_id_here
KALSHI_PROD_KEYFILE=/path/to/prod_private_key.pem

# ============================================
# DATABASE
# ============================================
DB_HOST=localhost
DB_PORT=5432
DB_NAME=precog_dev
DB_USER=postgres
DB_PASSWORD=your_password_here

# ============================================
# EXTERNAL APIs
# ============================================
# OpenWeatherMap (get from https://openweathermap.org/api)
OPENWEATHER_API_KEY=your_api_key_here

# Balldontlie (optional, get from https://balldontlie.io)
BALLDONTLIE_API_KEY=your_api_key_here

# ============================================
# DEVELOPMENT
# ============================================
# Development mode (true for local development)
DEV_MODE=true

# Log level (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL=DEBUG
```

### Step 7.5: Start First Task

According to PHASE_1_TASK_PLAN:

**First Task: Kalshi Authentication (Week 1)**

Create: `src/api_connectors/kalshi_auth.py`

Implement based on API_INTEGRATION_GUIDE_V2.0.md section on RSA-PSS authentication:

1. Read the API_INTEGRATION_GUIDE section on Kalshi auth
2. Implement `load_private_key()`
3. Implement `generate_signature()`
4. Implement `KalshiAuth` class
5. Write tests in `tests/api_connectors/test_kalshi_auth.py`
6. Verify tests pass

### Step 7.6: Development Cycle

For each Phase 1 task:

1. **Read requirements** from PHASE_1_TASK_PLAN
2. **Read API guide** for implementation details
3. **Write tests first** (TDD approach) or alongside code
4. **Implement feature** following coding standards
5. **Run tests** - must pass before moving on
6. **Commit changes** with descriptive message
7. **Move to next task**

### Step 7.7: Phase 1 Checklist

Track progress:

```markdown
# Phase 1 Implementation Checklist

## Week 1-2: Kalshi Authentication
- [ ] Implement kalshi_auth.py
- [ ] Implement kalshi_client.py (basic structure)
- [ ] Test authentication with demo environment
- [ ] Implement token refresh
- [ ] Tests passing (>80% coverage)

## Week 3-4: Database Setup
- [ ] Create database schema
- [ ] Implement connection pooling
- [ ] Implement ORM models
- [ ] Implement CRUD operations with SCD Type 2
- [ ] Tests passing

## Week 5: Configuration System
- [ ] Implement YAML config loading
- [ ] Implement DB override system
- [ ] Create config access utilities
- [ ] Tests passing

## Week 6: Integration & Testing
- [ ] Integration tests with real Kalshi demo
- [ ] End-to-end test: auth → fetch markets → store in DB
- [ ] Performance testing
- [ ] Documentation updates
- [ ] Code review
- [ ] Phase 1 complete! 🎉
```

---

## Summary of Instructions

This file contains comprehensive instructions for Claude Code to:

1. ✅ **Review** all Phase 0 documents for consistency
2. ✅ **Update** documents based on API_INTEGRATION_GUIDE_V2.0
3. ✅ **Verify** filename-version consistency
4. ✅ **Create** Developer Onboarding Guide
5. ✅ **Validate** Master Index for Phase 0 completeness
6. ✅ **Prepare** Git commit with all Phase 0 changes
7. ✅ **Kickoff** Phase 1 implementation

Each task has detailed steps, expected outputs, and success criteria.

---

## Ready to Execute

Save this file and provide it to Claude Code:

```bash
claude-code "Follow all instructions in CLAUDE_CODE_INSTRUCTIONS.md.
Work through each task systematically.
Create all required reports and documents.
Ask for clarification if any task is ambiguous."
```

Claude Code will work through everything and prepare your project for Phase 1! 🚀
