"""
Database Seeding Package.

Provides comprehensive seeding functionality for initializing and updating
static reference data in the database.

Key Components:
    - SeedingManager: Main class for orchestrating seeding operations
    - SeedCategory: Enum of data categories (teams, venues, Elo, etc.)
    - SeedingConfig: Configuration dataclass for customizing seeding

Usage:
    >>> from precog.database.seeding import SeedingManager, SeedCategory
    >>>
    >>> # Seed all data
    >>> manager = SeedingManager()
    >>> report = manager.seed_all()
    >>>
    >>> # Seed specific category
    >>> manager.seed_teams(sports=["nfl", "nba"])
    >>>
    >>> # Verify seeds exist
    >>> result = manager.verify_seeds()

Reference: Phase 2.5 - Live Data Collection Service
Related: ADR-029 (ESPN Data Model), REQ-DATA-003 (Multi-Sport Team Support)
"""

from precog.database.seeding.seeding_manager import (
    SeedCategory,
    SeedingConfig,
    SeedingManager,
    SeedingReport,
    SeedingStats,
    create_seeding_manager,
    seed_all_teams,
    verify_required_seeds,
)

__all__ = [
    "SeedCategory",
    "SeedingConfig",
    "SeedingManager",
    "SeedingReport",
    "SeedingStats",
    "create_seeding_manager",
    "seed_all_teams",
    "verify_required_seeds",
]
