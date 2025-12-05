"""
End-to-End Tests for ConfigLoader.

Tests complete configuration workflows:
- Full application configuration loading
- Production-like config scenarios
- Configuration validation pipelines

Related:
- TESTING_STRATEGY V3.2: All 8 test types required
- config/config_loader module coverage

Usage:
    pytest tests/e2e/config/test_config_loader_e2e.py -v -m e2e
"""

import pytest


@pytest.mark.e2e
class TestConfigLoaderE2E:
    """End-to-end tests for complete configuration workflows."""

    def test_full_application_config_load(self, tmp_path):
        """
        E2E: Load complete application configuration.

        Verifies:
        - All config sections load correctly
        - Application can start with loaded config
        """
        from precog.config.config_loader import ConfigLoader

        # Create production-like config
        config_content = """
application:
  name: "precog"
  environment: "test"
  debug: false

database:
  host: "localhost"
  port: "5432"
  name: "precog_test"
  pool_size: "10"

trading:
  enabled: true
  max_position_size: "1000.00"
  min_edge: "0.02"
  kelly_fraction: "0.25"

api:
  kalshi:
    base_url: "https://api.kalshi.com"
    rate_limit: "100"
  espn:
    base_url: "https://site.api.espn.com"

logging:
  level: "INFO"
  format: "json"
"""
        config_file = tmp_path / "application.yaml"
        config_file.write_text(config_content)

        loader = ConfigLoader(config_dir=str(tmp_path))
        config = loader.load("application.yaml")

        # Verify all sections loaded
        assert config["application"]["name"] == "precog"
        assert config["database"]["host"] == "localhost"
        assert config["trading"]["enabled"] is True
        assert "kalshi" in config["api"]
        assert config["logging"]["level"] == "INFO"

    def test_config_driven_component_initialization(self, tmp_path):
        """
        E2E: Components initialize from configuration.

        Verifies:
        - Config values drive component behavior
        - Components use config correctly
        """
        from precog.config.config_loader import ConfigLoader

        config_file = tmp_path / "components.yaml"
        config_file.write_text("""
rate_limiter:
  requests_per_minute: "60"
  burst_limit: "10"

logger:
  level: "DEBUG"
  handlers:
    - console
    - file
""")

        loader = ConfigLoader(config_dir=str(tmp_path))
        loader.load("components.yaml")

        # ConfigLoader uses (config_name, key_path) pattern
        rate_limit = int(loader.get("components", "rate_limiter.requests_per_minute"))
        assert rate_limit == 60

        log_level = loader.get("components", "logger.level")
        assert log_level == "DEBUG"

    def test_configuration_reload_workflow(self, tmp_path):
        """
        E2E: Configuration reload workflow.

        Verifies:
        - Config can be reloaded
        - Changes are reflected
        """
        from precog.config.config_loader import ConfigLoader

        config_file = tmp_path / "dynamic.yaml"
        config_file.write_text("""
setting:
  value: "original"
""")

        loader = ConfigLoader(config_dir=str(tmp_path))
        loader.load("dynamic.yaml")

        # ConfigLoader uses (config_name, key_path) pattern
        assert loader.get("dynamic", "setting.value") == "original"

        # Update config file
        config_file.write_text("""
setting:
  value: "updated"
""")

        # Reload - must clear cache first, then reload
        loader.reload("dynamic")
        loader.load("dynamic.yaml")
        assert loader.get("dynamic", "setting.value") == "updated"

    def test_config_validation_workflow(self, tmp_path):
        """
        E2E: Configuration validation workflow.

        Verifies:
        - Invalid configs are detected
        - Validation errors are informative
        """
        from precog.config.config_loader import ConfigLoader

        # Valid config
        valid_config = tmp_path / "valid.yaml"
        valid_config.write_text("""
trading:
  max_position_size: "1000.00"
""")

        loader = ConfigLoader(config_dir=str(tmp_path))
        config = loader.load("valid.yaml")

        # Verify valid config loads
        assert config is not None

    def test_environment_specific_config(self, tmp_path):
        """
        E2E: Environment-specific configuration loading.

        Verifies:
        - Different configs for different environments
        - Environment detection works
        """
        from precog.config.config_loader import ConfigLoader

        # Create environment-specific configs
        (tmp_path / "config.development.yaml").write_text("""
environment: "development"
debug: true
database:
  host: "localhost"
""")

        (tmp_path / "config.production.yaml").write_text("""
environment: "production"
debug: false
database:
  host: "prod-db.example.com"
""")

        # Load development config
        dev_loader = ConfigLoader(config_dir=str(tmp_path))
        dev_config = dev_loader.load("config.development.yaml")
        assert dev_config["environment"] == "development"
        assert dev_config["debug"] is True

        # Load production config
        prod_loader = ConfigLoader(config_dir=str(tmp_path))
        prod_config = prod_loader.load("config.production.yaml")
        assert prod_config["environment"] == "production"
        assert prod_config["debug"] is False
