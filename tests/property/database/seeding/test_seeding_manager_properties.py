"""
Property-Based Tests for Seeding Manager.

Uses Hypothesis to test seeding manager invariants and configuration handling.

Reference: TESTING_STRATEGY V3.2 - Property tests for business logic
Related Requirements: REQ-DATA-003, ADR-029

Usage:
    pytest tests/property/database/seeding/test_seeding_manager_properties.py -v -m property
"""

from unittest.mock import patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from precog.database.seeding import (
    SeedCategory,
    SeedingConfig,
    SeedingManager,
)

# =============================================================================
# Custom Strategies
# =============================================================================


# Valid sport codes
sport_strategy = st.sampled_from(["nfl", "ncaaf", "nba", "nhl", "wnba", "ncaab", "ncaaw"])

# Database environments
database_strategy = st.sampled_from(["dev", "test", "prod"])

# Season years
season_strategy = st.integers(min_value=2020, max_value=2030)

# Seed categories
category_strategy = st.sampled_from(list(SeedCategory))


# =============================================================================
# Property Tests: Configuration Invariants
# =============================================================================


@pytest.mark.property
class TestConfigurationInvariants:
    """Property tests for SeedingConfig invariants."""

    @given(
        sports=st.lists(sport_strategy, min_size=1, max_size=7, unique=True),
        database=database_strategy,
        dry_run=st.booleans(),
        use_api=st.booleans(),
        overwrite=st.booleans(),
    )
    @settings(max_examples=50)
    def test_config_preserves_all_settings(
        self,
        sports: list[str],
        database: str,
        dry_run: bool,
        use_api: bool,
        overwrite: bool,
    ) -> None:
        """Config should preserve all provided settings."""
        config = SeedingConfig(
            sports=sports,
            database=database,
            dry_run=dry_run,
            use_api=use_api,
            overwrite=overwrite,
        )

        assert config.sports == sports
        assert config.database == database
        assert config.dry_run == dry_run
        assert config.use_api == use_api
        assert config.overwrite == overwrite

    @given(
        categories=st.lists(category_strategy, min_size=1, max_size=6, unique=True),
    )
    @settings(max_examples=30)
    def test_config_categories_preserved(self, categories: list[SeedCategory]) -> None:
        """Config should preserve category list."""
        config = SeedingConfig(categories=categories)
        assert config.categories == categories

    @given(
        seasons=st.lists(season_strategy, min_size=1, max_size=5, unique=True),
    )
    @settings(max_examples=30)
    def test_config_seasons_preserved(self, seasons: list[int]) -> None:
        """Config should preserve season list."""
        config = SeedingConfig(seasons=seasons)
        assert config.seasons == seasons

    @given(st.data())
    @settings(max_examples=20)
    def test_config_mutable_defaults_isolated(self, data: st.DataObject) -> None:
        """Mutable defaults should be isolated between instances."""
        config1 = SeedingConfig()
        config2 = SeedingConfig()

        # Modify config1
        new_sport = data.draw(sport_strategy)
        if new_sport not in config1.sports:
            config1.sports.append(new_sport)

        # config2 should be unaffected
        assert len(config2.sports) == 7  # Default count


# =============================================================================
# Property Tests: Category Enum Invariants
# =============================================================================


@pytest.mark.property
class TestCategoryEnumInvariants:
    """Property tests for SeedCategory enum invariants."""

    @given(category=category_strategy)
    @settings(max_examples=20)
    def test_category_string_equality(self, category: SeedCategory) -> None:
        """Category should equal its string value."""
        assert category == category.value
        assert str(category.value) == category.value

    @given(
        category1=category_strategy,
        category2=category_strategy,
    )
    @settings(max_examples=30)
    def test_category_comparison_consistent(
        self, category1: SeedCategory, category2: SeedCategory
    ) -> None:
        """Category comparisons should be consistent."""
        if category1 == category2:
            assert category1.value == category2.value
        else:
            assert category1.value != category2.value


# =============================================================================
# Property Tests: Session Management
# =============================================================================


@pytest.mark.property
class TestSessionManagementInvariants:
    """Property tests for session management invariants."""

    @given(
        dry_run=st.booleans(),
    )
    @settings(max_examples=20)
    def test_session_start_initializes_state(self, dry_run: bool) -> None:
        """Session start should initialize all state."""
        config = SeedingConfig(dry_run=dry_run, use_api=False)
        manager = SeedingManager(config=config)

        manager._start_session()

        assert manager._session_id is not None
        assert manager._session_start is not None
        assert manager._category_stats == {}

    @given(
        dry_run=st.booleans(),
    )
    @settings(max_examples=20)
    def test_session_id_format_consistent(self, dry_run: bool) -> None:
        """Session ID should follow YYYYMMDD_HHMMSS format."""
        config = SeedingConfig(dry_run=dry_run, use_api=False)
        manager = SeedingManager(config=config)

        manager._start_session()

        session_id = manager._session_id
        assert session_id is not None
        assert len(session_id) == 15
        assert session_id[8] == "_"
        # Date part (YYYYMMDD)
        assert session_id[:8].isdigit()
        # Time part (HHMMSS)
        assert session_id[9:].isdigit()


# =============================================================================
# Property Tests: Statistics Invariants
# =============================================================================


@pytest.mark.property
class TestStatisticsInvariants:
    """Property tests for statistics calculation invariants."""

    @given(category=category_strategy)
    @settings(max_examples=20)
    def test_init_stats_zeroed(self, category: SeedCategory) -> None:
        """Initial stats should have all counts at zero."""
        config = SeedingConfig(use_api=False)
        manager = SeedingManager(config=config)

        stats = manager._init_stats(category)

        assert stats["records_processed"] == 0
        assert stats["records_created"] == 0
        assert stats["records_updated"] == 0
        assert stats["records_skipped"] == 0
        assert stats["errors"] == 0
        assert stats["last_error"] is None

    @given(category=category_strategy)
    @settings(max_examples=20)
    def test_empty_stats_matches_init_stats(self, category: SeedCategory) -> None:
        """Empty stats should match initial stats."""
        config = SeedingConfig(use_api=False)
        manager = SeedingManager(config=config)

        init_stats = manager._init_stats(category)
        empty_stats = manager._empty_stats(category)

        # Compare relevant fields (excluding timestamps)
        assert init_stats["records_processed"] == empty_stats["records_processed"]
        assert init_stats["records_created"] == empty_stats["records_created"]
        assert init_stats["errors"] == empty_stats["errors"]


# =============================================================================
# Property Tests: Report Aggregation
# =============================================================================


@pytest.mark.property
class TestReportAggregationInvariants:
    """Property tests for report aggregation invariants."""

    @given(
        sports=st.lists(sport_strategy, min_size=1, max_size=3, unique=True),
    )
    @settings(max_examples=20)
    def test_report_totals_match_sum(self, sports: list[str]) -> None:
        """Report totals should match sum of category stats."""
        with patch("precog.database.seeding.seeding_manager.get_cursor"):
            config = SeedingConfig(
                categories=[SeedCategory.TEAMS],
                sports=sports,
                dry_run=True,  # No actual DB access
                use_api=False,
            )
            manager = SeedingManager(config=config)

            report = manager.seed_all()

            # Totals should equal sum of category stats
            expected_processed = sum(
                s["records_processed"] for s in report["category_stats"].values()
            )
            expected_created = sum(s["records_created"] for s in report["category_stats"].values())
            expected_errors = sum(s["errors"] for s in report["category_stats"].values())

            assert report["total_records_processed"] == expected_processed
            assert report["total_records_created"] == expected_created
            assert report["total_errors"] == expected_errors

    @given(
        dry_run=st.booleans(),
    )
    @settings(max_examples=10)
    def test_report_success_reflects_errors(self, dry_run: bool) -> None:
        """Report success should be False if any errors occurred."""
        with patch("precog.database.seeding.seeding_manager.get_cursor"):
            config = SeedingConfig(
                categories=[SeedCategory.TEAMS],
                sports=["nfl"],
                dry_run=dry_run,
                use_api=False,
            )
            manager = SeedingManager(config=config)

            report = manager.seed_all()

            if report["total_errors"] > 0:
                assert report["success"] is False
            else:
                assert report["success"] is True


# =============================================================================
# Property Tests: Sport-Category Support
# =============================================================================


@pytest.mark.property
class TestSportCategorySupportInvariants:
    """Property tests for sport-category support invariants."""

    @given(category=category_strategy)
    @settings(max_examples=20)
    def test_category_has_sport_support(self, category: SeedCategory) -> None:
        """Every category should have defined sport support."""
        assert category in SeedingManager.SPORT_CATEGORY_SUPPORT
        assert isinstance(SeedingManager.SPORT_CATEGORY_SUPPORT[category], list)

    @given(sport=sport_strategy)
    @settings(max_examples=20)
    def test_all_sports_support_teams(self, sport: str) -> None:
        """All sports should support TEAMS category."""
        assert sport in SeedingManager.SPORT_CATEGORY_SUPPORT[SeedCategory.TEAMS]


# =============================================================================
# Property Tests: Manager Initialization
# =============================================================================


@pytest.mark.property
class TestManagerInitializationInvariants:
    """Property tests for manager initialization invariants."""

    @given(use_api=st.booleans())
    @settings(max_examples=10)
    def test_api_client_initialization(self, use_api: bool) -> None:
        """ESPN client should be created only when use_api=True."""
        with patch("precog.database.seeding.seeding_manager.ESPNClient") as mock_client:
            config = SeedingConfig(use_api=use_api)
            manager = SeedingManager(config=config)

            if use_api:
                mock_client.assert_called_once()
            else:
                mock_client.assert_not_called()
                assert manager.espn_client is None

    @given(
        database=database_strategy,
        sports=st.lists(sport_strategy, min_size=1, max_size=3, unique=True),
    )
    @settings(max_examples=20)
    def test_config_passed_to_manager(self, database: str, sports: list[str]) -> None:
        """Config should be accessible from manager."""
        config = SeedingConfig(database=database, sports=sports, use_api=False)
        manager = SeedingManager(config=config)

        assert manager.config.database == database
        assert manager.config.sports == sports


# =============================================================================
# Property Tests: Determinism
# =============================================================================


@pytest.mark.property
class TestDeterminismInvariants:
    """Property tests for deterministic behavior."""

    @given(
        sports=st.lists(sport_strategy, min_size=1, max_size=3, unique=True),
    )
    @settings(max_examples=10)
    def test_dry_run_deterministic(self, sports: list[str]) -> None:
        """Dry run should produce consistent results."""
        config = SeedingConfig(
            categories=[SeedCategory.TEAMS],
            sports=sports,
            dry_run=True,
            use_api=False,
        )

        manager1 = SeedingManager(config=config)
        manager2 = SeedingManager(config=config)

        # Both dry runs should succeed without errors
        report1 = manager1.seed_all()
        report2 = manager2.seed_all()

        assert report1["success"] == report2["success"]
        assert report1["total_errors"] == report2["total_errors"]
