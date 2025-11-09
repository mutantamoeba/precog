# PRECOG: Phase-Specific Implementation Checklists & Code Review Templates

---

## Table of Contents
1. Phase 1: Foundation Validation & API Integration Checklist
2. Phase 1.5: Foundation Enhancement & Versioning Checklist
3. Phase 2: Live Data Pipeline Checklist
4. Phase 3: Async Event Loop & Processing Checklist
5. Phase 4: Ensemble Modeling & Edge Detection Checklist
6. Phase 5: Position Monitoring & Trade Execution Checklist
7. Universal Code Review Template
8. Security & Infrastructure Review Template

---

## Phase 1: Foundation Validation & API Integration Checklist

**Timeline:** Weeks 7-12 | **Status:** 🟡 In Progress
**Objective:** Complete API clients, CLI commands, database validation, testing infrastructure.

### 1.1 Kalshi API Client Implementation
- [ ] **Authentication**: RSA-PSS key loading, token generation, signature validation.
  - [ ] Keys loaded from environment variables (never hardcoded).
  - [ ] Key rotation mechanism documented.
  - [ ] Signature verification tested with mock responses.
- [ ] **Endpoints Implemented**: Markets, orders, positions, event streams.
  - [ ] `GET /markets` - fetch market list with filters.
  - [ ] `POST /orders` - submit buy/sell orders.
  - [ ] `GET /orders/{order_id}` - retrieve order status.
  - [ ] `DELETE /orders/{order_id}` - cancel orders.
  - [ ] `GET /positions` - fetch current positions.
  - [ ] `WebSocket /events` - real-time event stream.
- [ ] **Error Handling & Retries**:
  - [ ] Exponential backoff for transient errors (5xx, timeouts).
  - [ ] Circuit breaker pattern for repeated failures (3 failures → 60s cooldown).
  - [ ] Max retries: 3 for API calls, 10 for critical operations.
  - [ ] Retry logic tested with mock failures.
- [ ] **Rate Limiting**:
  - [ ] Token bucket or adaptive rate limiting implemented.
  - [ ] Respect Kalshi rate limits (e.g., 10 req/sec).
  - [ ] Alert when approaching limits.
- [ ] **Logging & Instrumentation**:
  - [ ] All API calls logged with method, endpoint, status, latency.
  - [ ] Secrets (keys, tokens) masked in logs.
  - [ ] Errors logged with full context (request/response, retries).
- [ ] **Test Coverage**: ≥90% unit test coverage.
  - [ ] Mock API responses for all endpoints.
  - [ ] Test retry logic and exponential backoff.
  - [ ] Test rate limiting and circuit breakers.
  - [ ] Test error conditions (auth failures, invalid parameters, timeouts).

### 1.2 ESPN API Client Implementation
- [ ] **Data Endpoints**: Play-by-play, team stats, game status, schedule.
  - [ ] `GET /sports/football/leagues/nfl/events` - fetch games.
  - [ ] `GET /sports/football/leagues/nfl/events/{event_id}/competitions/{comp_id}` - game details.
  - [ ] `GET /sports/football/leagues/nfl/teams/{team_id}` - team info, schedule, stats.
- [ ] **Error Handling**: Same retry/circuit breaker logic as Kalshi.
- [ ] **Caching Strategy**:
  - [ ] Static data (team rosters, game schedules) cached with 24hr TTL.
  - [ ] Live game data cached with 1-2min TTL.
  - [ ] Cache invalidation on error responses.
- [ ] **Test Coverage**: ≥85% unit test coverage.
  - [ ] Mock ESPN responses for all endpoints.
  - [ ] Test caching behavior and TTL expiration.
  - [ ] Test error scenarios and cache fallback.

### 1.3 CLI Commands Implementation (Typer Framework)
- [ ] **Core Commands**:
  - [ ] `precog market list` - Display available markets with filters.
    - [ ] Shows market ID, name, status, current odds, liquidity.
    - [ ] Filters by sport, event type, status.
  - [ ] `precog position list` - Show current positions.
    - [ ] Displays position ID, quantity, entry price, current price, unrealized PnL.
  - [ ] `precog trade submit --market-id --side --quantity --limit-price` - Submit trade.
    - [ ] Validates inputs (positive quantity, valid side, reasonable price).
    - [ ] Displays order confirmation with ID and status.
  - [ ] `precog trade cancel --order-id` - Cancel pending order.
  - [ ] `precog monitor` - Real-time market and position monitoring.
    - [ ] Shows live market updates and position changes.
    - [ ] Refreshes every 2-5 seconds.
- [ ] **Documentation**:
  - [ ] `--help` works for all commands with full usage examples.
  - [ ] README.md includes CLI usage guide and examples.
- [ ] **Error Handling**:
  - [ ] User-friendly error messages (not stack traces).
  - [ ] Validation of all inputs with helpful error feedback.
- [ ] **Test Coverage**: ≥80% for CLI logic.
  - [ ] Test each command with valid and invalid inputs.
  - [ ] Test error scenarios gracefully handled.

### 1.4 Database Schema Validation (PostgreSQL)
- [ ] **Schema v1.5 Deployed**:
  - [ ] `markets`: ID, symbol, status, current_bid, current_ask, created_at, updated_at.
  - [ ] `orders`: ID, market_id, side, quantity, limit_price, filled_quantity, status, created_at, filled_at.
  - [ ] `positions`: ID, market_id, quantity, entry_price, current_price, created_at, updated_at.
  - [ ] `game_states`: game_id, timestamp, period, score_differential, time_remaining, possession_team, versioned metadata.
  - [ ] `versions`: entity_type, entity_id, version_number, created_at, data (JSONB).
- [ ] **Constraints & Indexes**:
  - [ ] Foreign key constraints enforced (no orphaned records).
  - [ ] Decimal precision for prices (e.g., numeric(10, 4) for odds).
  - [ ] Unique constraints where appropriate (no duplicate orders).
  - [ ] Indexes on frequently queried columns (market_id, order_id, status).
  - [ ] Test constraint violations (expected to fail).
- [ ] **Immutability Enforcement**:
  - [ ] Versioning system (SCD Type-2) working for configs/models.
  - [ ] INSERT-only audit tables (no UPDATE/DELETE).
  - [ ] Triggers preventing mutation of historical records.
- [ ] **Migration Management**:
  - [ ] All schema changes tracked in migrations/ folder.
  - [ ] Forward and backward migrations tested.
  - [ ] Migration tool (e.g., Alembic) configured and working.
- [ ] **Test Coverage**:
  - [ ] Integration tests validating schema integrity.
  - [ ] Test constraint enforcement and foreign keys.
  - [ ] Test versioning and immutability.

### 1.5 Configuration Management
- [ ] **YAML Config Loader**:
  - [ ] Loads config from `config.yaml` with schema validation (Pydantic).
  - [ ] Environment variable overrides work correctly.
  - [ ] Database overrides respect precedence (Env > DB > File).
  - [ ] Config validation catches missing/invalid fields early.
- [ ] **Config Categories**:
  - [ ] `api`: Kalshi/ESPN endpoints, rate limits, timeouts.
  - [ ] `database`: Connection string, pool size, SSL mode.
  - [ ] `trading`: Order size limits, position limits, circuit breaker thresholds.
  - [ ] `models`: Model paths, feature engineering params.
- [ ] **Secret Management**:
  - [ ] API keys, DB passwords loaded from environment variables.
  - [ ] `.env` file used locally (never committed to Git).
  - [ ] Kubernetes secrets for cloud deployment planned.
- [ ] **Test Coverage**: ≥85%.
  - [ ] Test config loading from YAML, environment, database.
  - [ ] Test precedence and override behavior.
  - [ ] Test validation errors for invalid configs.

### 1.6 Testing Infrastructure
- [ ] **Test Framework**: pytest configured and running.
  - [ ] `tests/` directory structure mirrors source code.
  - [ ] Fixtures for common test data (mock API responses, DB records).
  - [ ] Parametrized tests for multiple scenarios.
- [ ] **Coverage Reporting**: ≥80% target.
  - [ ] Coverage reports generated and tracked (e.g., coverage.py).
  - [ ] CI/CD pipeline enforces coverage gates.
- [ ] **Continuous Integration**:
  - [ ] GitHub Actions (or similar) configured.
  - [ ] CI runs on every pull request.
  - [ ] CI runs: linting (flake8), security (bandit), tests, coverage.
- [ ] **Mock Data & Fixtures**:
  - [ ] Mock Kalshi API responses for all endpoints.
  - [ ] Mock ESPN API responses.
  - [ ] Fixtures for database records.

### 1.7 Documentation & Handoff
- [ ] **API Documentation**:
  - [ ] Kalshi client documented with docstrings and examples.
  - [ ] ESPN client documented with docstrings and examples.
  - [ ] Request/response schemas defined.
- [ ] **CLI Documentation**:
  - [ ] README.md with CLI usage and examples.
  - [ ] `--help` output comprehensive.
- [ ] **Database Documentation**:
  - [ ] Schema diagram (ER diagram).
  - [ ] Table descriptions and column definitions.
  - [ ] Versioning system explained.
- [ ] **Developer Guide**:
  - [ ] Setup instructions (Python, PostgreSQL, dependencies).
  - [ ] Running tests and CI pipeline.
  - [ ] Common tasks (adding new API endpoint, adding config, adding test).
- [ ] **Code Review Completed**:
  - [ ] All code reviewed by at least one other person.
  - [ ] Issues resolved or documented.

### 1.8 Phase Completion Criteria
- ✅ All code changes merged with >80% test coverage.
- ✅ Documentation complete and reviewed.
- ✅ CI/CD pipeline passing.
- ✅ Kalshi API client fully functional and tested.
- ✅ ESPN API client fully functional and tested.
- ✅ CLI commands operational and documented.
- ✅ Database schema validated.
- ✅ Configuration system working end-to-end.

---

## Phase 1.5: Foundation Enhancement & Versioning Checklist

**Timeline:** Weeks 13-14 (after Phase 1) | **Status:** 🟡 Planned
**Objective:** Implement trade state machine, feature extraction, basic ensemble models.

### 1.5.1 Trade State Machine Implementation
- [ ] **States Defined**:
  - [ ] `PENDING`: Order submitted, awaiting execution.
  - [ ] `ACTIVE`: Order filled, position open.
  - [ ] `MONITORING`: Position held, monitoring for exits.
  - [ ] `EXIT_TRIGGERED`: Exit condition met, liquidating.
  - [ ] `CLOSED`: Position fully exited.
- [ ] **State Transitions**:
  - [ ] PENDING → ACTIVE (on partial/full fill).
  - [ ] PENDING → CANCELLED (on user cancel or timeout).
  - [ ] ACTIVE → MONITORING (automatically after fill).
  - [ ] MONITORING → EXIT_TRIGGERED (on exit condition).
  - [ ] EXIT_TRIGGERED → CLOSED (on liquidation completion).
- [ ] **Logging & Audit**:
  - [ ] All state transitions logged with timestamp, user, reason.
  - [ ] State changes stored in immutable audit table.
  - [ ] State machine events trigger alerts/notifications.
- [ ] **Test Coverage**: ≥90%.
  - [ ] Test all valid state transitions.
  - [ ] Test invalid transitions (error handling).
  - [ ] Test edge cases (concurrent state updates, network failures).

### 1.5.2 Feature Extraction Pipeline
- [ ] **Historical State Features**:
  - [ ] `score_differential`: Current margin (leader - trailer).
  - [ ] `time_remaining`: Minutes/seconds left in game.
  - [ ] `possession`: Team currently with ball (or neutral).
  - [ ] `down_distance`: Current down and yards to go (football-specific).
  - [ ] `field_position`: Yard line of ball (normalized 0-100).
  - [ ] Unit tests for feature calculation accuracy.
- [ ] **Team Strength Features**:
  - [ ] `elo_diff`: Elo rating difference between teams.
  - [ ] `home_advantage`: Binary or +/- adjustment factor.
  - [ ] `recent_performance`: Win rate last 5 games, net points differential.
  - [ ] Data source validation (Kalshi game_states table).
- [ ] **External Features**:
  - [ ] `weather`: Temperature, wind speed, precipitation (if available).
  - [ ] `injuries`: Key player absence indicator (boolean or impact score).
  - [ ] `line_movement`: Pregame line vs. current market odds.
  - [ ] `sharps_vs_public`: Betting volume trend indicator.
  - [ ] Data sources: ESPN API, weather APIs, betting aggregate sites.
- [ ] **Feature Validation**:
  - [ ] No NaN or infinite values (impute or drop).
  - [ ] Features normalized to reasonable ranges (e.g., 0-1 or z-scored).
  - [ ] Feature drift detection (e.g., sudden out-of-range values).
- [ ] **Feature Store**:
  - [ ] Features cached in PostgreSQL table or Redis.
  - [ ] TTL: 1-2 min for live game features, 1 day for static features.
  - [ ] Versioning: Track feature engineering version with each prediction.
- [ ] **Test Coverage**: ≥85%.
  - [ ] Unit tests for each feature calculation.
  - [ ] Integration tests for full pipeline.
  - [ ] Test with real historical data.

### 1.5.3 Basic Ensemble Models
- [ ] **Logistic Regression Baseline**:
  - [ ] Trained on historical game data with state features.
  - [ ] Outputs calibrated probability (0-1).
  - [ ] Cross-validated with 5-fold splits.
  - [ ] Accuracy: >50% on validation set.
- [ ] **Gradient Boosting (XGBoost)**:
  - [ ] Trained on same feature set as logistic regression.
  - [ ] Hyperparameter tuning via grid search or Bayesian optimization.
  - [ ] Feature importance extracted and logged.
  - [ ] Accuracy: >55% on validation set (expected to exceed logistic regression).
- [ ] **LSTM (Recurrent Neural Network)**:
  - [ ] Trains on sequence of game states (play-by-play or time steps).
  - [ ] Captures temporal dynamics (momentum, trend).
  - [ ] Output: probability prediction.
  - [ ] Accuracy: >55% on validation set.
- [ ] **Model Calibration**:
  - [ ] Calibration curves plotted for each model.
  - [ ] Isotonic regression or temperature scaling applied if needed.
  - [ ] Predictions validate (e.g., 70% prediction accuracy ≈ 70% actual win rate in bin).
- [ ] **Model Versioning**:
  - [ ] Each trained model stored with version ID, training date, hyperparams.
  - [ ] Models serialized (pickle, joblib, or ONNX) and stored in S3 or local `models/` folder.
  - [ ] Version tracked in `model_versions` table.
- [ ] **Test Coverage**: ≥80%.
  - [ ] Unit tests for model training pipeline.
  - [ ] Integration tests for end-to-end prediction.
  - [ ] Backtesting on held-out historical data.

### 1.5.4 Backtesting Harness
- [ ] **Replay Engine**:
  - [ ] Loads historical play-by-play and market data.
  - [ ] Simulates feature extraction at each time step.
  - [ ] Simulates model prediction.
  - [ ] Simulates order submission and fill (using actual Kalshi data or realistic fill simulation).
- [ ] **Performance Metrics**:
  - [ ] Win rate: % of trades with positive return.
  - [ ] Sharpe ratio: risk-adjusted return.
  - [ ] Max drawdown: peak-to-trough decline.
  - [ ] Sortino ratio: downside risk adjusted.
  - [ ] Average latency per prediction.
- [ ] **Reporting**:
  - [ ] Generate backtest report (CSV, HTML, or Markdown).
  - [ ] Include performance curves (equity, drawdown, win rate over time).
  - [ ] Include trade log (all trades with entry, exit, PnL).
- [ ] **Walk-Forward Validation**:
  - [ ] Split data into rolling windows (e.g., 80% train, 20% test).
  - [ ] Retrain model on each window, test on hold-out.
  - [ ] Aggregate performance across windows (out-of-sample).
- [ ] **Test Coverage**: ≥80%.
  - [ ] Unit tests for replay engine.
  - [ ] Integration tests for backtesting pipeline.
  - [ ] Verify backtest results match manual calculations.

### 1.5.5 Documentation & Handoff
- [ ] **State Machine Documentation**:
  - [ ] Diagram showing states and transitions.
  - [ ] Example walkthrough of trade lifecycle.
- [ ] **Feature Engineering Guide**:
  - [ ] Explanation of each feature, data source, calculation.
  - [ ] Validation checks documented.
  - [ ] Feature importance from XGBoost visualized.
- [ ] **Model Documentation**:
  - [ ] Hyperparameters and rationale for each model.
  - [ ] Training data characteristics (size, date range, distribution).
  - [ ] Validation results and cross-validation strategy.
  - [ ] Calibration curves and interpretation.
- [ ] **Backtesting Guide**:
  - [ ] How to run backtest and interpret results.
  - [ ] Walk-forward methodology explained.
  - [ ] Example backtest report included.

### 1.5.6 Phase Completion Criteria
- ✅ State machine fully implemented and tested.
- ✅ Feature extraction pipeline validated with >85% test coverage.
- ✅ Logistic regression, XGBoost, LSTM models trained and >50% baseline accuracy.
- ✅ Backtesting harness operational with walk-forward validation.
- ✅ >80% test coverage across new components.
- ✅ Documentation complete and reviewed.

---

## Phase 2: Live Data Pipeline Checklist

**Timeline:** Weeks 15-18 | **Status:** ⏳ Not Started
**Objective:** Ingest live ESPN and Kalshi data, validate quality, store in PostgreSQL.

### 2.1 Kalshi Event Stream (WebSocket)
- [ ] **Connection Management**:
  - [ ] WebSocket connection to Kalshi `events` endpoint.
  - [ ] Automatic reconnection on disconnect (exponential backoff).
  - [ ] Heartbeat/ping-pong to detect stale connections.
  - [ ] Connection metrics logged (uptime, reconnections, latency).
- [ ] **Event Parsing**:
  - [ ] Parse market updates (price changes, liquidity).
  - [ ] Parse order events (fills, rejections, cancellations).
  - [ ] Parse position updates.
  - [ ] Handle malformed events gracefully (log, skip, alert).
- [ ] **Data Validation**:
  - [ ] Timestamp validation (no future dates, reasonable age).
  - [ ] Price/quantity validation (positive, within reasonable range).
  - [ ] Deduplication (ignore duplicate events).
- [ ] **Storage**:
  - [ ] Insert events into PostgreSQL `market_events` table.
  - [ ] Batch inserts for efficiency (500-1000 per batch).
  - [ ] Log storage failures and retry.
- [ ] **Test Coverage**: ≥80%.
  - [ ] Mock WebSocket events and test parsing.
  - [ ] Test reconnection logic.
  - [ ] Test data validation and deduplication.

### 2.2 ESPN Live Game Data
- [ ] **API Polling**:
  - [ ] Poll ESPN API every 10-30 seconds for active games.
  - [ ] Extract play-by-play updates and game state.
  - [ ] Update `game_states` table with latest state.
- [ ] **Data Extraction**:
  - [ ] Current score, time remaining, possession, down/distance.
  - [ ] Play sequence (drives, plays, scoring).
  - [ ] Team stats (yards, turnovers, etc.).
- [ ] **Data Validation**:
  - [ ] Consistency checks (score never decreases mid-game, time decreases monotonically).
  - [ ] Sanity checks (score not unreasonably high, reasonable clock values).
  - [ ] Deduplication (ignore repeated states).
- [ ] **Storage**:
  - [ ] Insert state into `game_states` table with versioning.
  - [ ] SCD Type-2 captures all state changes.
  - [ ] Index on `game_id, timestamp` for efficient queries.
- [ ] **Test Coverage**: ≥80%.
  - [ ] Mock ESPN API responses.
  - [ ] Test data extraction and validation.
  - [ ] Test versioning system.

### 2.3 Data Quality & Monitoring
- [ ] **Data Freshness**:
  - [ ] Monitor time lag between market data timestamp and ingestion.
  - [ ] Alert if lag >5 minutes (indicating outage or slowdown).
  - [ ] Track metrics: mean lag, max lag, freshness SLA.
- [ ] **Completeness**:
  - [ ] Verify all expected events received (no gaps in game states).
  - [ ] Alert on missing events or long gaps.
- [ ] **Accuracy**:
  - [ ] Spot-check ingested data against source APIs.
  - [ ] Validate data consistency (e.g., Kalshi market prices match ESPN game state).
- [ ] **Logging**:
  - [ ] Log ingestion rate (events/sec).
  - [ ] Log errors, retries, skipped records.
  - [ ] Log data quality metrics to time-series DB.

### 2.4 Phase Completion Criteria
- ✅ Kalshi WebSocket connection stable and real-time data flowing.
- ✅ ESPN API polling retrieving live game data.
- ✅ Data validated and stored in PostgreSQL with versioning.
- ✅ Data quality monitoring operational.
- ✅ >80% test coverage.

---

## Phase 3: Async Event Loop & Processing Checklist

**Timeline:** Weeks 19-22 | **Status:** ⏳ Not Started
**Objective:** Build async event loop for real-time feature computation and model inference.

### 3.1 Async Event Loop Architecture
- [ ] **Event Queue**:
  - [ ] Market data events queued (Kafka, Redis, or in-memory queue).
  - [ ] Events processed in order, with ordering guarantees per market.
- [ ] **Feature Computation**:
  - [ ] On each market event, compute updated features.
  - [ ] Cache features for quick access.
  - [ ] Log feature computation time.
- [ ] **Model Inference**:
  - [ ] On feature update, run ensemble model inference.
  - [ ] Output prediction (probability, confidence).
  - [ ] Log inference time and result.
- [ ] **Edge Detection**:
  - [ ] Compare model prediction to market odds.
  - [ ] Calculate EV+ if edge exists.
  - [ ] Queue trade if EV+ > threshold.
- [ ] **Async Correctness**:
  - [ ] All I/O (API, DB) non-blocking (asyncio, aiohttp).
  - [ ] No blocking calls in event loop.
  - [ ] Proper error handling and exception propagation.
  - [ ] Resource cleanup (connection pooling, graceful shutdown).

### 3.2 Failover & Resilience
- [ ] **REST API Fallback**:
  - [ ] If WebSocket disconnects, fall back to REST API polling.
  - [ ] Graceful degradation of latency (polling slower than streaming).
  - [ ] Automatic switchover back to WebSocket when restored.
- [ ] **Data Validation**:
  - [ ] Detect corrupted or stale data; discard.
  - [ ] Skip inference if data quality insufficient.
- [ ] **Circuit Breakers**:
  - [ ] Break circuit if model inference fails consistently.
  - [ ] Stop trading until circuit recovered.
  - [ ] Log circuit breaker events.

### 3.3 Performance Optimization
- [ ] **Latency Targets**:
  - [ ] End-to-end latency (market event → trade decision): <2 seconds target.
  - [ ] Feature computation: <500ms.
  - [ ] Model inference: <200ms.
  - [ ] Trade submission: <100ms.
- [ ] **Profiling & Monitoring**:
  - [ ] Profile code to identify bottlenecks.
  - [ ] Monitor latency at each stage (feature, model, trade).
  - [ ] Alert if latency exceeds thresholds.
- [ ] **Concurrency**:
  - [ ] Process multiple markets concurrently.
  - [ ] Avoid cross-market contention (lock-free or fine-grained locks).
  - [ ] Load test with realistic market volume.

### 3.4 Test Coverage
- [ ] **Unit Tests**: ≥80% coverage.
  - [ ] Test event processing and queuing.
  - [ ] Test feature computation with mock data.
  - [ ] Test model inference and edge detection.
- [ ] **Integration Tests**:
  - [ ] Test full event loop with simulated market data.
  - [ ] Test failover from WebSocket to REST.
  - [ ] Test circuit breaker triggering.
- [ ] **Load Tests**:
  - [ ] Simulate high market volume (100s of events/sec).
  - [ ] Verify latency and throughput remain acceptable.

### 3.5 Phase Completion Criteria
- ✅ Async event loop operational and tested.
- ✅ Feature computation <500ms, model inference <200ms.
- ✅ Failover mechanisms working.
- ✅ >80% test coverage.

---

## Phase 4: Ensemble Modeling & Edge Detection Checklist

**Timeline:** Weeks 23-30 | **Status:** ⏳ Not Started
**Objective:** Implement stacked ensemble, dynamic weighting, EV+ quantification.

### 4.1 Advanced Ensemble Models
- [ ] **Diverse Base Learners**:
  - [ ] Logistic Regression (fast, interpretable baseline).
  - [ ] XGBoost (nonlinear feature interactions).
  - [ ] LSTM (temporal dynamics).
  - [ ] Bayesian GLM (uncertainty quantification).
  - [ ] Domain models (Elo + heuristics).
- [ ] **Model Calibration**:
  - [ ] Calibration curves plotted for each model.
  - [ ] Temperature scaling or isotonic regression applied.
  - [ ] Cross-validation on calibration (separate holdout set).
- [ ] **Test Coverage**: ≥80%.
  - [ ] Unit tests for each base model.
  - [ ] Integration tests for ensemble inference.

### 4.2 Dynamic Weighting & Regime Detection
- [ ] **Regime Segmentation**:
  - [ ] Define market regimes (e.g., high variance, low variance, trending, ranging).
  - [ ] Detect regime changes using statistical tests (e.g., Augmented Dickey-Fuller).
  - [ ] Classify current market state to regime.
- [ ] **Meta-Learner**:
  - [ ] Train logistic regression or small NN to weight base models.
  - [ ] Use base model predictions and meta-features as inputs.
  - [ ] Separate training per regime.
  - [ ] Retrain meta-learner weekly or on regime change.
- [ ] **Dynamic Weights**:
  - [ ] Weights adapt to current regime.
  - [ ] Track weight changes and alert on significant shifts.
  - [ ] Log ensemble composition for each prediction.
- [ ] **Test Coverage**: ≥80%.
  - [ ] Unit tests for regime detection.
  - [ ] Integration tests for dynamic weighting.
  - [ ] Backtest ensemble vs. individual models.

### 4.3 EV+ Quantification & Kelly Criterion
- [ ] **EV Calculation**:
  - [ ] EV = (Model Probability × Payout) - (1 - Model Probability) × Bet.
  - [ ] Account for vig/commission.
  - [ ] Account for transaction costs (if any).
  - [ ] EV+ threshold (e.g., >2% edge required to trade).
- [ ] **Kelly Criterion**:
  - [ ] Kelly Fraction = (Probability × Payout - 1) / (Payout - 1).
  - [ ] Fractional Kelly (e.g., 0.5x Kelly) for conservative sizing.
  - [ ] Apply Kelly to position size calculation.
- [ ] **Confidence Integration**:
  - [ ] Use model confidence to adjust Kelly fraction.
  - [ ] Low confidence → reduce fraction; high confidence → full fraction.
- [ ] **Test Coverage**: ≥85%.
  - [ ] Unit tests for EV calculation.
  - [ ] Unit tests for Kelly formula.
  - [ ] Integration tests for position sizing.

### 4.4 Backtesting Enhancement
- [ ] **Multi-Regime Backtesting**:
  - [ ] Backtest ensemble with dynamic weighting.
  - [ ] Compare to static weighting and individual models.
  - [ ] Analyze performance per regime.
- [ ] **Walk-Forward Validation**:
  - [ ] Retrain ensemble on rolling windows.
  - [ ] Out-of-sample performance aggregated.
  - [ ] Verify backtest results match live performance expectations.
- [ ] **Sensitivity Analysis**:
  - [ ] Vary Kelly fraction (0.25x to 1.0x) and show trade-offs.
  - [ ] Vary EV+ threshold and show impact.
  - [ ] Document robustness to parameter changes.

### 4.5 Phase Completion Criteria
- ✅ 5+ base learners trained and calibrated.
- ✅ Meta-learner and dynamic weighting operational.
- ✅ Regime detection and adaptation working.
- ✅ EV+ and Kelly sizing implemented.
- ✅ Ensemble outperforms individual models in backtest.
- ✅ >80% test coverage.

---

## Phase 5: Position Monitoring & Trade Execution Checklist

**Timeline:** Weeks 31-34 | **Status:** ⏳ Not Started
**Objective:** Implement real-time position monitoring, exit strategy, and price walking.

### 5.1 Position Lifecycle Management
- [ ] **Position Tracking**:
  - [ ] Track all open positions with entry price, quantity, entry time.
  - [ ] Mark-to-market PnL updated in real-time.
  - [ ] Position metrics logged (quantity, duration, current odds).
- [ ] **Exit Conditions** (10 prioritized):
  - [ ] 1. Profit Target Hit: Exit if profit > Kelly predicted profit.
  - [ ] 2. Stop Loss: Exit if loss > threshold (e.g., -20% of position).
  - [ ] 3. Time Decay: Exit if confidence decays over time (e.g., after 20 min).
  - [ ] 4. Model Divergence: Exit if ensemble reversion to 50% (no longer favorable).
  - [ ] 5. Liquidity Evaporation: Exit if bid-ask spread widens >threshold.
  - [ ] 6. Correlated Risk: Exit if correlated position reaches portfolio limit.
  - [ ] 7. API/System Failure: Exit on error detection (failsafe).
  - [ ] 8. Portfolio Drawdown: Exit if portfolio drawdown >threshold.
  - [ ] 9. Volatility Spike: Exit if realized volatility >threshold.
  - [ ] 10. Scheduled Exit: Exit at predefined time (e.g., game end + 1hr).
- [ ] **Exit Evaluation**:
  - [ ] Evaluate all exit conditions in priority order every 10-30 sec.
  - [ ] Execute first triggered condition.
  - [ ] Log condition, decision, action.

### 5.2 Price Walking Algorithm
- [ ] **Multi-Stage Execution**:
  - [ ] Stage 1: Aggressive (close to market price, faster fill).
  - [ ] Stage 2: Moderate (midpoint, balance speed/price).
  - [ ] Stage 3: Conservative (deep in book, patience for better price).
- [ ] **Urgency-Based Stepping**:
  - [ ] Early urgency (exit signal but not time-critical): Step slowly, try for better price.
  - [ ] High urgency (near game end or critical error): Step aggressively, prioritize fill.
  - [ ] Critical urgency (failsafe): Market order to liquidate immediately.
- [ ] **Partial Fill Management**:
  - [ ] Accept partial fills; continue stepping for remainder.
  - [ ] Monitor fill rate and adjust strategy if slow.
- [ ] **Test Coverage**: ≥80%.
  - [ ] Unit tests for exit condition evaluation.
  - [ ] Unit tests for price walking logic.
  - [ ] Integration tests with simulated market responses.

### 5.3 Real-Time Monitoring & Alerting
- [ ] **Position Dashboard**:
  - [ ] Display all open positions with key metrics.
  - [ ] Show exit condition status for each position.
  - [ ] Update every 2-5 sec in real-time.
- [ ] **Performance Monitoring**:
  - [ ] KPI tracking: daily PnL, Sharpe ratio, max drawdown, win rate.
  - [ ] Trend analysis over daily, weekly, monthly periods.
  - [ ] Compare live performance to backtest expectations.
- [ ] **Alert System**:
  - [ ] Alert on portfolio drawdown >15%, >25%, >35%.
  - [ ] Alert on error/exception spike.
  - [ ] Alert on API latency >2 sec.
  - [ ] Alert on execution slippage >50bps.
- [ ] **Logging**:
  - [ ] All position updates logged with timestamp, user, reason.
  - [ ] All alerts logged with severity and action taken.
  - [ ] Immutable audit trail maintained.

### 5.4 Phase Completion Criteria
- ✅ Position lifecycle management fully implemented.
- ✅ 10 exit conditions evaluated and working.
- ✅ Price walking algorithm tested with realistic scenarios.
- ✅ Real-time monitoring dashboard operational.
- ✅ Alert system functional.
- ✅ >80% test coverage.
- ✅ Live trading in micro-size (paper trading) successful for 2+ weeks.

---

## Universal Code Review Template

**Use for all pull requests. Requires sign-off from at least one reviewer.**

### Code Quality
- [ ] Code follows PEP 8 style guide (or documented deviation).
- [ ] Variable names clear and descriptive.
- [ ] Functions/classes have docstrings explaining purpose, inputs, outputs.
- [ ] Complex logic commented.
- [ ] No dead code, debug statements, or commented-out code.
- [ ] Complexity reasonable (functions <50 lines, classes <500 lines).

### Security & Secrets
- [ ] No hardcoded secrets (API keys, passwords, tokens).
- [ ] No PII in logs or error messages.
- [ ] Inputs validated and sanitized.
- [ ] No SQL injection vulnerabilities (use parameterized queries).
- [ ] HTTPS/TLS used for all external APIs.

### Financial Accuracy
- [ ] All numerical operations use `Decimal` (no float for money).
- [ ] Precision validated (e.g., prices to 4 decimal places).
- [ ] Rounding behavior explicit and documented.
- [ ] Edge cases tested (zero amounts, very large amounts, negative amounts).

### Async & Concurrency
- [ ] All I/O operations awaitable (non-blocking).
- [ ] No blocking calls in async functions.
- [ ] Error handling in async code (try/except around awaits).
- [ ] Resource cleanup (close connections, cancel tasks).

### Database Operations
- [ ] Parameterized queries used (no string concatenation).
- [ ] Foreign keys and constraints respected.
- [ ] Indexes used for large table scans.
- [ ] Transactions used where appropriate (ACID).
- [ ] No N+1 query patterns.

### Testing
- [ ] Unit tests present for new code.
- [ ] Tests cover happy path, error cases, edge cases.
- [ ] Mock external dependencies (APIs, databases).
- [ ] Test failures clear and actionable.
- [ ] Tests run and pass locally and in CI/CD.

### Documentation
- [ ] Changes documented (docstrings, comments, README updates).
- [ ] New config options documented.
- [ ] New requirements tracked in requirements.txt or poetry.lock.
- [ ] Breaking changes flagged and explained.

### Performance
- [ ] No obvious performance regressions.
- [ ] Latency-sensitive code profiled and optimized.
- [ ] Large loops have reasonable complexity (O(n) preferred, O(n²) rare).
- [ ] Memory usage reasonable (no leaks or excessive allocations).

### Error Handling
- [ ] Expected errors caught and handled gracefully.
- [ ] Errors logged with context (not swallowed).
- [ ] User-facing errors clear and actionable (not stack traces).
- [ ] Failsafe mode for critical failures.

### Architecture & Design
- [ ] Changes align with documented architecture.
- [ ] Modularity maintained (low coupling, high cohesion).
- [ ] No circular dependencies.
- [ ] SOLID principles respected (single responsibility, open/closed, etc.).

### Version Control
- [ ] Commit messages clear and descriptive.
- [ ] Commits logically grouped (one feature per commit if possible).
- [ ] PR description explains "why" (not just "what").
- [ ] No merge conflicts or rebasing issues.

### Reviewer Sign-Off
- [ ] Reviewer 1: ________ (Date: ______)
- [ ] Reviewer 2 (if complex): ________ (Date: ______)
- [ ] Approved for merge: ☐ Yes ☐ No
- [ ] Comments/Action Items:
  - ...

---

## Security & Infrastructure Review Template

**Use for infrastructure, deployment, configuration, and security-related changes.**

### API Security
- [ ] Authentication enforced (OAuth, API key, JWT).
- [ ] Authorization checks in place (role-based access).
- [ ] Input validation and sanitization.
- [ ] Rate limiting configured.
- [ ] HTTPS/TLS 1.3 enforced.
- [ ] Certificate pinning considered.

### Database Security
- [ ] Connections use TLS (sslmode=require).
- [ ] Role-based permissions configured (app_user, admin_user).
- [ ] Passwords strong and rotated regularly.
- [ ] Encryption at rest considered.
- [ ] Audit logging enabled (pgaudit).
- [ ] Backups automated and tested.

### Secrets Management
- [ ] Secrets in environment variables or vault (never in code).
- [ ] .env files ignored by Git.
- [ ] CI/CD secrets stored in platform (GitHub Actions, GitLab, etc.).
- [ ] No secrets in logs or error messages.
- [ ] Key rotation policy documented.

### Infrastructure & Deployment
- [ ] Minimal Docker base images (alpine, python:slim).
- [ ] Container runs as non-root user.
- [ ] Network policies restrict traffic (only necessary ports).
- [ ] Firewall rules minimal (deny-all, allow necessary).
- [ ] VPC/subnets properly isolated.

### Monitoring & Alerting
- [ ] Logs centralized and searchable.
- [ ] Error/exception alerts configured.
- [ ] Security events (failed logins, unauthorized access) alerted.
- [ ] Performance degradation monitored.
- [ ] Uptime/SLA tracked.

### Compliance & Audit
- [ ] Data retention policies enforced.
- [ ] PII handling documented and compliant.
- [ ] Audit trail maintained for all sensitive operations.
- [ ] Regulatory requirements met (if applicable).
- [ ] Compliance documentation reviewed.

### Dependencies & Supply Chain
- [ ] Dependencies checked for vulnerabilities (pip-audit).
- [ ] Dependency versions pinned (not wildcard).
- [ ] License compliance verified.
- [ ] Third-party service terms reviewed.

### Reviewer Sign-Off
- [ ] Security Lead: ________ (Date: ______)
- [ ] Infrastructure Lead: ________ (Date: ______)
- [ ] Approved for deployment: ☐ Yes ☐ No
- [ ] Security Issues/Action Items:
  - ...

---

**Version:** 1.0
**Last Updated:** November 8, 2025
**Status:** Ready for Use
**Author:** Technical Architecture Review
