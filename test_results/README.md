# Test Results Storage

This directory stores test execution results with timestamps for historical tracking.

## Structure

```
test_results/
├── latest/                    # Symlink to most recent run (Unix only)
├── 2025-10-29_143022/        # Timestamped test run
│   ├── pytest_report.html    # HTML test report
│   ├── test_output.log       # Terminal output
│   └── metadata.json         # Run metadata (future)
├── 2025-10-29_091534/
│   └── ...
└── README.md                  # This file
```

## Viewing Results

### Latest Test Run

```bash
# View HTML report (Unix/Mac)
open test_results/latest/pytest_report.html

# View HTML report (Windows)
start test_results/latest/pytest_report.html

# View log
cat test_results/latest/test_output.log
```

### Specific Test Run

```bash
# List all runs
ls test_results/

# View specific run
open test_results/2025-10-29_143022/pytest_report.html
```

## Coverage Reports

Coverage reports are stored separately in `htmlcov/`:

```bash
# View coverage report
open htmlcov/index.html  # (Unix/Mac)
start htmlcov/index.html  # (Windows)
```

## Gitignore

- **Timestamped runs:** NOT committed (too large, regenerated each run)
- **history.json:** COMMITTED (small, valuable trend data)

See `.gitignore` for details.

## Retention

- **Local:** Keep last 30 days manually
- **CI/CD:** GitHub Actions retains 30 days automatically

## Automated Test Runs

Test results are saved automatically when running:

```bash
# Full test suite (saves to test_results/)
./scripts/test_full.sh

# Quick tests (no result saving)
./scripts/test_fast.sh
```

## Metadata (Future)

Future enhancement: `metadata.json` will track:
- Timestamp
- Duration
- Test counts (passed/failed/skipped)
- Coverage percentage
- Git commit hash
- Phase

See: Phase 0.7 enhancements

---

**Questions?** See `docs/foundation/TESTING_STRATEGY_V2.0.md`
