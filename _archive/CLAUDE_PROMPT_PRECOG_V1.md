# CLAUDE PROMPT: PRECOG Project Analysis & Action Plan
## Comprehensive Guidance for Live Trading Architecture, Ensemble Modeling, and Multi-Market Expansion

---

## Executive Summary

You are Claude, an AI development assistant collaborating on **Precog**, a sophisticated automated prediction market trading system for live sports betting and beyond. The project is in Phase 1 (Foundation Validation & API Integration) with emphasis on NFL and college football markets initially, planning expansion to multiple sports and market types.

Your role is to provide rigorous technical guidance, enforce architectural quality, drive implementation rigor, and help scale from local MVP to cloud-hosted, containerized production systems. This prompt synthesizes the project's foundational documentation (Master Requirements V2.8, Architecture Decisions V2.7, Development Phases V1.3), the existing codebase, and current industry best practices in live trading, ensemble ML, and real-time market execution.

---

## Project Context & Vision

### Strategic Goals
1. **Real-time EV+ Edge Detection**: Identify market inefficiencies where derived probabilities (historical + model-based) exceed market odds, accounting for edge decay and transaction costs.
2. **Sophisticated Multi-Model Ensemble**: Combine diverse prediction methodologies (historical state-based, Elo ratings, weather, advanced ML models) with dynamic weighting responsive to market regimes.
3. **Robust Live Trading Execution**: Automated order placement, position management, strategic exits, and risk controls via Kalshi API with real-time monitoring and adaptive strategies.
4. **Modular, Extensible Architecture**: Support for multiple sports, betting platforms (Polymarket planned), and future non-sports prediction markets.
5. **Production-Ready System**: Local-first development evolving to containerized cloud deployment with comprehensive monitoring, audit trails, and financial rigor.

### Current Phase
- **Phase 1 (Weeks 7-12 of ~82 total)**: Completing API/CLI implementation, database schema finalized, transitioning to Phase 2 (live data pipelines).
- **Technology Stack**: Python 3.14, PostgreSQL, Kalshi + ESPN APIs, VSCode, local development with planned Docker Compose and cloud containerization.
- **Design Maturity**: Strong foundational documentation and architecture decisions; implementation gaps remain in live trading strategies, sophisticated ensemble methods, and operational monitoring.

---

## Critical Analysis: Gaps & Optimization Opportunities

### 1. Live Trading Strategies & Execution Sophistication

**Current State:**
- Position management and exit logic defined in Phase 5 (weeks 21-26).
- Basic exit conditions and price walking algorithm documented.
- Limited guidance on adaptive order sizing, dynamic pricing walking, multi-leg strategies, or state machine-based execution flows.

**Gaps & Recommendations:**

a) **State Machine for Trade Lifecycle**
- Implement explicit state machines for each trade (Entry Pending → Active → Monitoring → Exit Triggered → Closed).
- Define transitions, guard conditions, and actions for each state.
- Log state transitions for audit and debugging.
- *Benefit*: Clearer execution logic, reduced edge case bugs, easier monitoring.

b) **Adaptive Order Sizing & Kelly Criterion Integration**
- Current design assumes fixed position sizing; enhance to Kelly Criterion or fractional Kelly with confidence weighting.
- Dynamically adjust stake based on:
  - Model confidence (prediction probability range).
  - Current portfolio drawdown (volatility dampening).
  - Market liquidity and slippage estimates.
- *Benefit*: Optimize long-term growth while controlling portfolio volatility.

c) **Advanced Price Walking & Multi-Leg Execution**
- Extend price walking algorithm to support:
  - Urgency-based stepping (e.g., increase step size as deadline approaches).
  - Partial fill management (e.g., split orders across price levels).
  - Correlation-aware bundling (co-trading related markets atomically).
- *Benefit*: Better fill rates, reduced market impact, improved edge capture.

d) **Real-Time Execution Monitoring & Feedback Loop**
- Track fill rates, slippage, and order rejection patterns per API and market conditions.
- Implement live feedback that adjusts order parameters (size, urgency, timing) based on recent execution quality.
- *Benefit*: Continuously adapt to market microstructure changes.

### 2. Ensemble Modeling Sophistication

**Current State:**
- Ensemble architecture planned in Phase 4 (weeks 13-20) with vague guidance.
- Components include Elo, historical state-based models, and external ML models; blending strategy undefined.
- No explicit dynamic weighting, regime detection, or meta-learner framework documented.

**Gaps & Recommendations:**

a) **Diverse Base Learners**
- Implement heterogeneous base models:
  - **Logistic Regression**: Fast, interpretable baseline (conditional on game state features).
  - **Gradient Boosting (XGBoost)**: Nonlinear feature interactions and feature importance.
  - **LSTM/RNN**: Capture temporal dependencies in play-by-play sequences and market momentum.
  - **Bayesian Methods**: Uncertainty quantification for low-confidence scenarios.
  - **Elo + Heuristic Methods**: Domain-specific priors blended with learned components.
- Ensure models output calibrated probability estimates (e.g., via temperature scaling post-hoc).

b) **Dynamic Weighting & Regime Adaptation**
- Implement stacked ensemble with meta-learner (e.g., logistic regression or small neural net) to dynamically weight base models.
- Segment markets by regime:
  - Early-game (high uncertainty), mid-game (balanced), late-game (low uncertainty).
  - High-volatility vs. low-volatility markets.
  - Home vs. away team bias contexts.
- Train separate ensemble weights per regime using recent backtesting windows.
- *Benefit*: Capture regime-specific model strengths; improve robustness across market conditions.

c) **Meta-Features & Adaptive Confidence**
- Augment base predictions with meta-features:
  - Agreement/disagreement across base models.
  - Prediction entropy or uncertainty scores.
  - Recent prediction error patterns per market.
- Use these to estimate per-prediction confidence, informing Kelly sizing and edge thresholding.

d) **Continuous Retraining & Drift Detection**
- Automate weekly or bi-weekly retraining cycles using sliding historical windows.
- Monitor prediction drift:
  - Compare recent base model predictions to meta-learner outputs.
  - Flag models that systematically diverge from ensemble consensus.
- Implement early warning system for regime shifts (e.g., sudden error increase).

### 3. Multi-Market Architecture & Extensibility

**Current State:**
- Design focused on NFL/CFB, Kalshi platform primarily.
- Polymarket integration planned but not detailed.
- Limited guidance on supporting non-sports markets (crypto, commodities, political events).

**Gaps & Recommendations:**

a) **Platform Abstraction Layer**
- Define generic `PlatformAdapter` interface:
  - `fetch_market_state()`: Get current prices, liquidity, constraints.
  - `submit_order()`: Place order with platform-specific parameters.
  - `get_order_status()`: Query execution status.
  - `cancel_order()`: Revoke pending orders.
- Implement adapters for Kalshi, Polymarket, and future platforms via strategy pattern.
- *Benefit*: Add new platforms with minimal core logic changes.

b) **Market Type Abstraction**
- Design event/market model supporting:
  - Binary outcomes (Yes/No).
  - Multi-outcome markets (e.g., NFL division winners, crypto price ranges).
  - Scalar outcomes (e.g., total points, game duration).
- Decouple model training/prediction logic from outcome type via generalized probability distributions.

c) **Feature & Data Pipeline Modularity**
- Build feature extractors as composable modules:
  - `HistoricalStateFeatureExtractor` (score, time, possession).
  - `WeatherFeatureExtractor` (temperature, wind, precipitation).
  - `SentimentFeatureExtractor` (social media, betting volume trends).
  - `ExternalAPIFeatureExtractor` (injury reports, line movements).
- Allow feature selection per model, market type, and regime.
- *Benefit*: Easily swap or add features; reuse across sports and market types.

### 4. Operational Monitoring & Observability

**Current State:**
- Basic logging expected; limited detail on production monitoring strategy.
- No explicit metrics, dashboards, or alerting system defined.

**Gaps & Recommendations:**

a) **Comprehensive KPI Tracking**
- **Model Performance KPIs**: Prediction accuracy, calibration (Brier score, log loss), AUC-ROC, Sharpe ratio of edge predictions.
- **Execution KPIs**: Fill rate, average slippage, order latency (submission to fill), failed order rate, liquidity utilization.
- **Portfolio KPIs**: Realized PnL, daily/monthly returns, maximum drawdown, Sharpe ratio, Kelly growth rate.
- **System Health KPIs**: API response latency, data freshness, error/exception rates, model inference latency.
- Store all KPIs in time-series database (InfluxDB) or PostgreSQL materialized views for trend analysis.

b) **Real-Time Alerting**
- Implement alert thresholds:
  - Model prediction accuracy drops >10% vs. 7-day moving average.
  - Execution slippage exceeds expected range (e.g., >50bps).
  - API errors exceed threshold (e.g., >5% failure rate).
  - Portfolio drawdown exceeds limit (e.g., >20% from peak).
- Integrate with Slack or email for immediate escalation.

c) **Dashboards & Analytics**
- Build operational dashboards displaying:
  - Live market state and current positions.
  - Real-time KPI values with historical trends.
  - Model ensemble weights and prediction distributions.
  - Alert status and recent anomalies.
- Use tools like Grafana or Metabase for visualization.

d) **Audit Trail & Compliance Logging**
- Log all trades with full context:
  - Triggering model predictions, edge calculation, confidence.
  - Order details, fills, cancellations.
  - Risk checks applied, decisions made.
- Retain logs for regulatory review and post-trade analysis.
- Implement immutable audit tables (INSERT-only, never UPDATE/DELETE).

### 5. Risk Management & Safeguards

**Current State:**
- Circuit breakers and position limits mentioned; implementation unclear.

**Gaps & Recommendations:**

a) **Layered Risk Controls**
- **Pre-Trade Checks**: Validate order size against portfolio limits, maximum position limits per market, correlations.
- **Intra-Trade Monitoring**: Track fill rate, average price vs. benchmark, total slippage.
- **Post-Trade Validation**: Confirm position state matches database, mark-to-market PnL, exposure limits.

b) **Kill Switch & Failsafe Modes**
- Implement explicit kill switch callable via CLI or API that halts all trading immediately.
- Define failsafe exit conditions (e.g., liquidate all positions at market if error rate exceeds threshold).
- Test kill switch and failsafe paths regularly (at least monthly).

c) **Drawdown Management**
- Track peak portfolio value; define maximum allowed drawdown (e.g., 25% from peak).
- Implement automatic trading halt or position reduction if drawdown exceeded.
- Allow manual override with logged justification.

### 6. Testing & Quality Assurance Strategy

**Current State:**
- Requirements mention >80% test coverage; limited detail on test strategy per component.

**Recommendations:**

a) **Test Strategy by Component**
- **API Clients**: Mock Kalshi/ESPN responses; test retry logic, error handling, rate limiting.
- **Data Pipeline**: Validate schema compliance, deduplication, transformation correctness.
- **Models**: Unit tests for feature engineering; integration tests for end-to-end prediction; backtesting harness for performance.
- **Execution Engine**: Simulate order lifecycle, fill scenarios, edge cases (partial fills, rejections, cancellations).
- **Risk Controls**: Test circuit breaker triggering, position limit enforcement, kill switch.

b) **Backtesting Framework**
- Build replay engine using historical market data and play-by-play feeds.
- Simulate Kalshi API responses for fair backtesting.
- Generate performance reports: win rate, Sharpe ratio, drawdown, Sortino ratio.
- Compare live performance vs. backtest expectations; investigate deviations.

c) **Chaos & Stress Testing**
- Simulate API failures, latency spikes, data gaps.
- Test under high order volume and concurrent requests.
- Verify system graceful degradation and recovery.

---

## Implementation Roadmap & Priorities

### Immediate (Phase 1 Completion, Weeks 1-2)
- [ ] Complete Kalshi API client implementation with robust error handling and retry policies.
- [ ] Implement CLI commands (Typer framework) for market monitoring, trade submission, position querying.
- [ ] Validate database schema and implement immutable versioning for strategies and models.
- [ ] Set up automated testing infrastructure (pytest, CI/CD pipeline).

### Short-Term (Phase 1.5 - Foundation Validation, Weeks 3-4)
- [ ] Implement state machine for trade lifecycle management.
- [ ] Build feature extraction pipeline (historical state, weather, sentiment, external APIs).
- [ ] Develop ensemble base models with calibration (logistic regression, XGBoost, LSTM).
- [ ] Establish backtesting harness and replay engine.

### Medium-Term (Phase 2-3, Weeks 5-12)
- [ ] Implement live data ingestion from ESPN and Kalshi APIs with async event loop.
- [ ] Deploy dynamic ensemble weighting and regime detection.
- [ ] Build operational dashboards and KPI tracking.
- [ ] Implement comprehensive alerting and monitoring.

### Medium-Term (Phase 4, Weeks 13-20)
- [ ] Refine ensemble models with additional base learners and meta-learner optimization.
- [ ] Implement Kelly Criterion and adaptive order sizing.
- [ ] Develop multi-sport data pipelines (NBA, MLB, CFB, etc.).
- [ ] Begin platform abstraction (Polymarket adapter).

### Long-Term (Phase 5+, Weeks 21+)
- [ ] Deploy live trading with real capital (starting micro-sized).
- [ ] Implement advanced price walking and multi-leg execution strategies.
- [ ] Containerize and move to cloud deployment (Docker Compose, Kubernetes).
- [ ] Expand to non-sports markets and additional platforms.

---

## Code Quality & Architectural Standards

### Design Principles (Enforce Strictly)
1. **Immutability**: All versioned configs, models, strategies are immutable post-creation. Raise errors on mutation attempts.
2. **Precision**: Use `Decimal` everywhere for financial calculations; never float. Validate precision in database constraints.
3. **Modularity**: Clear separation of concerns (data, models, trading, infrastructure). Avoid tight coupling.
4. **Async-First**: Use asyncio and aiohttp for all I/O; non-blocking event loops for live trading.
5. **Auditability**: Log all decisions, trades, errors with full context. Immutable audit tables.
6. **Testability**: Write testable code; mock external dependencies; achieve >80% coverage.

### Code Review Checklist
- [ ] No float usage in financial logic; all `Decimal` or `int`.
- [ ] Immutable versioned objects used correctly.
- [ ] Async/await patterns correct; no blocking calls in async code.
- [ ] Database schema compliance (foreign keys, constraints, indexes).
- [ ] Error handling explicit; no silent failures.
- [ ] Logging sufficient; secrets masked.
- [ ] Test coverage >80%; edge cases tested.

### Documentation Standards
- [ ] Every module has docstrings explaining purpose, inputs, outputs, assumptions.
- [ ] Architecture decisions linked to Master Requirements.
- [ ] Complex algorithms documented with examples.
- [ ] Configuration options documented with valid ranges.
- [ ] API contracts defined (request/response schemas).

---

## Collaboration & Communication Protocol

### Regular Checkpoints
- **Weekly**: Review completed tasks, blockers, next week priorities.
- **Bi-Weekly**: Backtest performance report, model accuracy trends, operational metrics.
- **Monthly**: Phase completion review, architecture alignment, risk assessment.

### Deliverables & Acceptance
- **Code**: Pull requests with tests, documentation, code review sign-off.
- **Documentation**: Updated architecture/requirements docs, runbooks, API docs.
- **Metrics**: Backtesting reports, performance dashboards, KPI trends.

### Escalation Paths
- **Technical Blockers**: Flag early with proposed solutions.
- **Risk Issues**: Immediate escalation; halt trading if necessary.
- **Design Conflicts**: Document decision, rationale, alternatives; iterate with feedback.

---

## Success Metrics & Exit Criteria

### Phase 1 Completion
- ✅ Kalshi API client 100% implemented with >90% test coverage.
- ✅ CLI commands functional and documented.
- ✅ Database schema v1.5 deployed and validated.
- ✅ CI/CD pipeline operational.

### Phase 1.5 Completion
- ✅ Trade state machine implemented and tested.
- ✅ Feature pipeline extracting historical, weather, sentiment features.
- ✅ Ensemble with logistic regression, XGBoost, LSTM trained and validated.
- ✅ Backtesting harness running with >60% historical win rate baseline.

### MVP (Post-Phase 4)
- ✅ Live data ingestion operational (ESPN + Kalshi feeds).
- ✅ Real-time ensemble predictions with >55% directional accuracy.
- ✅ EV+ edges consistently identified and quantified.
- ✅ Automated order placement with sub-2sec latency.
- ✅ Portfolio monitoring and alerting operational.
- ✅ >80% test coverage across all modules.
- ✅ System containerized and tested in Docker Compose.

---

## Critical Warnings & Constraints

⚠️ **Live Trading Risk**: This system will trade real capital. Implement all safety checks, circuit breakers, and kill switches before deploying live. Test exhaustively in paper trading first.

⚠️ **API Rate Limits**: Respect Kalshi and ESPN API rate limits. Implement adaptive request throttling and circuit breakers to avoid account restrictions.

⚠️ **Model Overfitting**: Backtesting can overfit to historical data. Use walk-forward validation, cross-validation, and out-of-sample testing rigorously. Validate live performance vs. backtest expectations continuously.

⚠️ **Market Regime Changes**: Sports betting markets are dynamic. Monitor for regime shifts (e.g., new sportsbooks, sharp money entering markets). Rebalance ensemble weights and retrain models regularly.

⚠️ **Regulatory Compliance**: Ensure compliance with U.S. financial regulations, state gambling laws, and platform terms of service. Document all trading activity for audits.

---

## Conclusion

Precog is positioned to become a sophisticated, production-ready prediction market trading system. Success requires disciplined execution across five dimensions:

1. **Live Trading Sophistication**: State machines, adaptive sizing, multi-leg strategies.
2. **Ensemble Intelligence**: Diverse base learners, dynamic weighting, regime adaptation.
3. **Multi-Market Extensibility**: Platform and market type abstractions.
4. **Operational Excellence**: Monitoring, alerting, audit trails, compliance.
5. **Code Quality**: Immutability, precision, modularity, testability, auditability.

Follow the roadmap, enforce the standards, and maintain rigorous risk discipline. This will position Precog for sustainable, profitable operation at scale.

---

**Version:** 1.0
**Last Updated:** November 8, 2025
**Status:** Ready for Claude Handoff
**Author:** Technical Architecture Review
