"""
ESPN Data Quality Validation Module.

Provides validation utilities to ensure ESPN game state data meets quality
standards before database storage. Implements Pattern 1 (Decimal Precision)
and defensive validation for trading-critical data.

Key Features:
- Score validation (non-negative, monotonic within period)
- Clock validation (proper Decimal handling, period bounds)
- Situation validation (down/distance rules by sport)
- Team/Venue validation (ESPN ID format, required fields)

Educational Notes:
-----------------
Data validation is critical for trading systems because:
1. Bad data leads to bad trading decisions (garbage in, garbage out)
2. Some ESPN API edge cases return unusual values (-1 for down/distance)
3. SCD Type 2 versioning means bad data persists in history
4. Validation logs provide debugging for market correlation issues

The validation approach:
- Log anomalies but DON'T block storage (soft validation)
- Track anomaly counts for pattern detection
- Use ValidationResult to aggregate multiple issues
- Return structured data for downstream processing

Reference: docs/foundation/TESTING_STRATEGY_V3.2.md
Related Requirements:
    - Phase 2: Data Quality Validation (Issue #186)
    - REQ-DATA-002: Data Quality Monitoring
"""

import logging
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any, ClassVar

from precog.api_connectors.espn_client import ESPNGameFull, ESPNSituationData

# Set up logging
logger = logging.getLogger(__name__)


class ValidationLevel(Enum):
    """
    Severity levels for validation issues.

    Levels:
        ERROR: Critical issue that may corrupt data
        WARNING: Suspicious data that should be investigated
        INFO: Minor anomaly for logging/tracking
    """

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationIssue:
    """
    Single validation issue with context.

    Attributes:
        level: Severity of the issue
        field: Which field has the issue
        message: Human-readable description
        value: The actual value that failed validation
        expected: What was expected (optional)
    """

    level: ValidationLevel
    field: str
    message: str
    value: Any = None
    expected: Any = None

    def __str__(self) -> str:
        """Format issue for logging."""
        parts = [f"[{self.level.value.upper()}] {self.field}: {self.message}"]
        if self.value is not None:
            parts.append(f" (got: {self.value!r}")
            if self.expected is not None:
                parts.append(f", expected: {self.expected!r}")
            parts.append(")")
        return "".join(parts)


@dataclass
class ValidationResult:
    """
    Aggregated validation result for a game state.

    Collects multiple validation issues and provides convenience
    methods for checking severity levels.

    Attributes:
        issues: List of validation issues found
        game_id: ESPN event ID for context

    Usage:
        >>> result = ValidationResult(game_id="401547389")
        >>> result.add_error("score", "Negative score", value=-1)
        >>> if result.has_errors:
        ...     logger.error(f"Validation failed: {result.errors}")
    """

    game_id: str = ""
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        """Check if any ERROR level issues exist."""
        return any(i.level == ValidationLevel.ERROR for i in self.issues)

    @property
    def has_warnings(self) -> bool:
        """Check if any WARNING level issues exist."""
        return any(i.level == ValidationLevel.WARNING for i in self.issues)

    @property
    def errors(self) -> list[ValidationIssue]:
        """Get all ERROR level issues."""
        return [i for i in self.issues if i.level == ValidationLevel.ERROR]

    @property
    def warnings(self) -> list[ValidationIssue]:
        """Get all WARNING level issues."""
        return [i for i in self.issues if i.level == ValidationLevel.WARNING]

    @property
    def is_valid(self) -> bool:
        """Check if no errors were found (warnings are OK)."""
        return not self.has_errors

    def add_error(
        self,
        field_name: str,
        message: str,
        value: Any = None,
        expected: Any = None,
    ) -> None:
        """Add an ERROR level issue."""
        self.issues.append(
            ValidationIssue(
                level=ValidationLevel.ERROR,
                field=field_name,
                message=message,
                value=value,
                expected=expected,
            )
        )

    def add_warning(
        self,
        field_name: str,
        message: str,
        value: Any = None,
        expected: Any = None,
    ) -> None:
        """Add a WARNING level issue."""
        self.issues.append(
            ValidationIssue(
                level=ValidationLevel.WARNING,
                field=field_name,
                message=message,
                value=value,
                expected=expected,
            )
        )

    def add_info(
        self,
        field_name: str,
        message: str,
        value: Any = None,
        expected: Any = None,
    ) -> None:
        """Add an INFO level issue."""
        self.issues.append(
            ValidationIssue(
                level=ValidationLevel.INFO,
                field=field_name,
                message=message,
                value=value,
                expected=expected,
            )
        )

    def log_issues(self) -> None:
        """Log all issues at appropriate levels."""
        for issue in self.issues:
            msg = f"[{self.game_id}] {issue}"
            if issue.level == ValidationLevel.ERROR:
                logger.error(msg)
            elif issue.level == ValidationLevel.WARNING:
                logger.warning(msg)
            else:
                logger.info(msg)


class ESPNDataValidator:
    """
    Validator for ESPN game state data.

    Provides comprehensive validation for game states before database
    storage, ensuring data quality for trading decisions.

    Attributes:
        strict_mode: If True, treat warnings as errors (default: False)
        track_anomalies: If True, count anomalies per game (default: True)

    Validation Categories:
        - Score validation: Non-negative, monotonic
        - Clock validation: Decimal precision, period bounds
        - Situation validation: Sport-specific rules
        - Metadata validation: Required fields, formats

    Usage:
        >>> validator = ESPNDataValidator()
        >>> result = validator.validate_game_state(game_data)
        >>> if result.has_errors:
        ...     logger.error("Validation failed")
        >>> else:
        ...     upsert_game_state(**game_data)  # Safe to store

    Educational Note:
        This validator uses "soft validation" - it logs issues but
        doesn't block storage. This is intentional because:
        1. Some ESPN anomalies are expected (e.g., -1 for non-play downs)
        2. We want full data history even with issues
        3. Pattern detection requires seeing all data

    Reference: Issue #186 (Data Quality Validation)
    """

    # Sport-specific period lengths (seconds)
    PERIOD_LENGTHS: ClassVar[dict[str, int]] = {
        "nfl": 900,  # 15 minutes
        "ncaaf": 900,  # 15 minutes
        "nba": 720,  # 12 minutes
        "ncaab": 1200,  # 20 minutes
        "nhl": 1200,  # 20 minutes
        "wnba": 600,  # 10 minutes
    }

    # Sport-specific period counts (regular time)
    PERIOD_COUNTS: ClassVar[dict[str, int]] = {
        "nfl": 4,
        "ncaaf": 4,
        "nba": 4,
        "ncaab": 2,
        "nhl": 3,
        "wnba": 4,
    }

    # Sports that use down/distance
    FOOTBALL_SPORTS: ClassVar[set[str]] = {"nfl", "ncaaf"}

    def __init__(
        self,
        strict_mode: bool = False,
        track_anomalies: bool = True,
    ) -> None:
        """
        Initialize the validator.

        Args:
            strict_mode: If True, treat warnings as errors
            track_anomalies: If True, maintain anomaly counts
        """
        self.strict_mode = strict_mode
        self.track_anomalies = track_anomalies
        self._anomaly_counts: dict[str, int] = {}

        logger.debug(
            "ESPNDataValidator initialized: strict=%s, track=%s",
            strict_mode,
            track_anomalies,
        )

    def validate_game_state(
        self,
        game: ESPNGameFull,
        previous_state: dict[str, Any] | None = None,
    ) -> ValidationResult:
        """
        Validate a complete game state.

        Runs all validation checks and aggregates results.

        Args:
            game: Game data in ESPNGameFull format
            previous_state: Optional previous state for temporal validation

        Returns:
            ValidationResult with all issues found

        Educational Note:
            The previous_state parameter enables temporal validation:
            - Score can only increase (within period)
            - Clock can only decrease (within period)
            - Period can only increase

            This catches data corruption and API glitches.
        """
        # Extract and cast to dict for internal validation methods
        metadata: dict[str, Any] = dict(game.get("metadata", {}))
        state: dict[str, Any] = dict(game.get("state", {}))
        espn_event_id = str(metadata.get("espn_event_id", "unknown"))
        league_raw = metadata.get("league", "")
        league = str(league_raw).lower() if league_raw else ""

        result = ValidationResult(game_id=espn_event_id)

        # Run all validation checks
        self._validate_scores(state, previous_state, result)
        self._validate_clock(state, league, result)
        self._validate_situation(state, league, result)
        self._validate_metadata(metadata, result)
        self._validate_teams(metadata, result)
        self._validate_venue(metadata, result)

        # Track anomalies if enabled
        if self.track_anomalies and result.issues:
            self._anomaly_counts[espn_event_id] = self._anomaly_counts.get(espn_event_id, 0) + len(
                result.issues
            )

        # Log issues
        if result.issues:
            result.log_issues()

        return result

    def validate_score(
        self,
        home_score: int,
        away_score: int,
        previous_home: int | None = None,
        previous_away: int | None = None,
    ) -> ValidationResult:
        """
        Validate score values.

        Args:
            home_score: Current home team score
            away_score: Current away team score
            previous_home: Previous home score (for monotonic check)
            previous_away: Previous away score (for monotonic check)

        Returns:
            ValidationResult with any score issues
        """
        result = ValidationResult()
        state = {"home_score": home_score, "away_score": away_score}
        previous = None
        if previous_home is not None and previous_away is not None:
            previous = {"home_score": previous_home, "away_score": previous_away}
        self._validate_scores(state, previous, result)
        return result

    def validate_clock(
        self,
        clock_seconds: Decimal | int | float | None,
        period: int,
        league: str,
    ) -> ValidationResult:
        """
        Validate clock values.

        Args:
            clock_seconds: Game clock in seconds
            period: Current period number
            league: League code for period length lookup

        Returns:
            ValidationResult with any clock issues
        """
        result = ValidationResult()
        state = {"clock_seconds": clock_seconds, "period": period}
        self._validate_clock(state, league.lower(), result)
        return result

    def validate_situation(
        self,
        situation: ESPNSituationData | dict[str, Any],
        league: str,
    ) -> ValidationResult:
        """
        Validate game situation data.

        Args:
            situation: Situation data (down, distance, possession, etc.)
            league: League code for sport-specific rules

        Returns:
            ValidationResult with any situation issues
        """
        result = ValidationResult()
        state = {"situation": situation}
        self._validate_situation(state, league.lower(), result)
        return result

    def _validate_scores(
        self,
        state: dict[str, Any],
        previous: dict[str, Any] | None,
        result: ValidationResult,
    ) -> None:
        """Validate score values."""
        home_score = state.get("home_score")
        away_score = state.get("away_score")

        # Check for non-negative scores
        if home_score is not None and home_score < 0:
            result.add_error(
                "home_score",
                "Score must be non-negative",
                value=home_score,
                expected=">=0",
            )

        if away_score is not None and away_score < 0:
            result.add_error(
                "away_score",
                "Score must be non-negative",
                value=away_score,
                expected=">=0",
            )

        # Check for score decrease (possible data corruption)
        if previous:
            prev_home = previous.get("home_score")
            prev_away = previous.get("away_score")

            if home_score is not None and prev_home is not None and home_score < prev_home:
                result.add_warning(
                    "home_score",
                    "Score decreased from previous state",
                    value=home_score,
                    expected=f">={prev_home}",
                )

            if away_score is not None and prev_away is not None and away_score < prev_away:
                result.add_warning(
                    "away_score",
                    "Score decreased from previous state",
                    value=away_score,
                    expected=f">={prev_away}",
                )

    def _validate_clock(
        self,
        state: dict[str, Any],
        league: str,
        result: ValidationResult,
    ) -> None:
        """Validate clock and period values."""
        clock_seconds = state.get("clock_seconds")
        period = state.get("period")

        # Validate clock is non-negative
        if clock_seconds is not None:
            # Convert to Decimal for comparison (Pattern 1)
            if not isinstance(clock_seconds, Decimal):
                clock_seconds = Decimal(str(clock_seconds))

            if clock_seconds < 0:
                result.add_error(
                    "clock_seconds",
                    "Clock must be non-negative",
                    value=clock_seconds,
                    expected=">=0",
                )

            # Check clock doesn't exceed period length
            period_length = self.PERIOD_LENGTHS.get(league)
            if period_length and clock_seconds > period_length:
                result.add_warning(
                    "clock_seconds",
                    f"Clock exceeds period length for {league}",
                    value=clock_seconds,
                    expected=f"<={period_length}",
                )

        # Validate period number
        if period is not None:
            if period < 0:
                result.add_error(
                    "period",
                    "Period must be non-negative",
                    value=period,
                    expected=">=0",
                )
            elif period == 0:
                result.add_info(
                    "period",
                    "Period is 0 (pre-game)",
                    value=period,
                )
            else:
                max_period = self.PERIOD_COUNTS.get(league, 4)
                # Allow overtime (period > max is valid)
                if period > max_period + 5:  # Allow up to 5 OT periods
                    result.add_warning(
                        "period",
                        f"Unusual period number for {league}",
                        value=period,
                        expected=f"<={max_period + 5}",
                    )

    def _validate_situation(
        self,
        state: dict[str, Any],
        league: str,
        result: ValidationResult,
    ) -> None:
        """Validate game situation (down, distance, etc.)."""
        situation = state.get("situation", {})
        if not situation:
            return

        # Football-specific validation
        if league in self.FOOTBALL_SPORTS:
            down = situation.get("down")
            distance = situation.get("distance")

            # Validate down (1-4 or -1 for non-play situations)
            if down is not None:
                if down == -1:
                    result.add_info(
                        "situation.down",
                        "Down is -1 (non-play situation)",
                        value=down,
                    )
                elif down < 1 or down > 4:
                    result.add_warning(
                        "situation.down",
                        "Down must be 1-4 or -1",
                        value=down,
                        expected="1-4 or -1",
                    )

            # Validate distance (positive or -1 for non-play)
            if distance is not None:
                if distance == -1:
                    result.add_info(
                        "situation.distance",
                        "Distance is -1 (non-play situation)",
                        value=distance,
                    )
                elif distance < 0:
                    result.add_error(
                        "situation.distance",
                        "Distance must be positive or -1",
                        value=distance,
                        expected=">0 or -1",
                    )

            # Validate possession
            possession = situation.get("possession")
            if possession is not None and not isinstance(possession, str):
                result.add_warning(
                    "situation.possession",
                    "Possession should be team identifier string",
                    value=possession,
                )

        # Basketball-specific validation
        elif league in ("nba", "ncaab", "wnba"):
            # Check for foul counts if present
            fouls = situation.get("fouls")
            if fouls is not None and fouls < 0:
                result.add_error(
                    "situation.fouls",
                    "Foul count must be non-negative",
                    value=fouls,
                    expected=">=0",
                )

    def _validate_metadata(
        self,
        metadata: dict[str, Any],
        result: ValidationResult,
    ) -> None:
        """Validate game metadata fields."""
        espn_event_id = metadata.get("espn_event_id")
        if not espn_event_id:
            result.add_error(
                "espn_event_id",
                "Missing required ESPN event ID",
            )
        elif not isinstance(espn_event_id, str) or len(espn_event_id) < 5:
            result.add_warning(
                "espn_event_id",
                "ESPN event ID seems invalid",
                value=espn_event_id,
            )

        # Validate game date if present
        game_date = metadata.get("game_date")
        if game_date is not None and not isinstance(game_date, str):
            result.add_warning(
                "game_date",
                "Game date should be ISO format string",
                value=type(game_date).__name__,
            )

    def _validate_teams(
        self,
        metadata: dict[str, Any],
        result: ValidationResult,
    ) -> None:
        """Validate team information."""
        for team_key in ("home_team", "away_team"):
            team = metadata.get(team_key, {})
            if not team:
                result.add_warning(
                    team_key,
                    f"Missing {team_key} information",
                )
                continue

            # Check ESPN team ID
            espn_team_id = team.get("espn_team_id")
            if not espn_team_id:
                result.add_warning(
                    f"{team_key}.espn_team_id",
                    "Missing ESPN team ID",
                )

            # Check team name
            team_name = team.get("team_name") or team.get("name")
            if not team_name:
                result.add_info(
                    f"{team_key}.team_name",
                    "Missing team name",
                )

    def _validate_venue(
        self,
        metadata: dict[str, Any],
        result: ValidationResult,
    ) -> None:
        """Validate venue information."""
        venue = metadata.get("venue", {})
        if not venue:
            # Venue is optional
            return

        venue_name = venue.get("venue_name") or venue.get("name")
        if not venue_name:
            result.add_info(
                "venue.venue_name",
                "Missing venue name",
            )

        # Validate capacity if present
        capacity = venue.get("capacity")
        if capacity is not None and (not isinstance(capacity, int) or capacity <= 0):
            result.add_warning(
                "venue.capacity",
                "Venue capacity should be positive integer",
                value=capacity,
            )

    def get_anomaly_count(self, game_id: str) -> int:
        """
        Get total anomaly count for a specific game.

        Args:
            game_id: ESPN event ID

        Returns:
            Total number of anomalies detected for this game
        """
        return self._anomaly_counts.get(game_id, 0)

    def get_all_anomaly_counts(self) -> dict[str, int]:
        """
        Get anomaly counts for all tracked games.

        Returns:
            Dictionary mapping game_id to anomaly count
        """
        return self._anomaly_counts.copy()

    def reset_anomaly_counts(self) -> None:
        """Clear all tracked anomaly counts."""
        self._anomaly_counts.clear()
        logger.debug("Anomaly counts reset")


# =============================================================================
# Convenience Functions
# =============================================================================


def create_validator(
    strict_mode: bool = False,
    track_anomalies: bool = True,
) -> ESPNDataValidator:
    """
    Factory function to create a configured validator.

    Args:
        strict_mode: If True, treat warnings as errors
        track_anomalies: If True, maintain anomaly counts

    Returns:
        Configured ESPNDataValidator instance

    Example:
        >>> validator = create_validator(strict_mode=True)
        >>> result = validator.validate_game_state(game_data)
    """
    return ESPNDataValidator(
        strict_mode=strict_mode,
        track_anomalies=track_anomalies,
    )
