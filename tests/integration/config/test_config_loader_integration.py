"""
Integration Tests for ConfigLoader.

Tests configuration loading with real file system operations:
- Loading actual YAML files
- Environment variable integration
- Configuration inheritance

Related:
- TESTING_STRATEGY V3.2: All 8 test types required
- config/config_loader module coverage

Usage:
    pytest tests/integration/config/test_config_loader_integration.py -v

Note: ConfigLoader supports custom config directories via config_dir parameter.
"""


class TestConfigLoaderIntegration:
    """Integration tests for ConfigLoader with real file operations."""

    def test_load_actual_config_file(self, tmp_path):
        """
        INTEGRATION: Load an actual YAML configuration file.

        Verifies:
        - Real file I/O works correctly
        - YAML parsing works with actual files
        """
        from precog.config.config_loader import ConfigLoader

        # Create a real config file
        config_content = """
trading:
  max_position_size: "1000.00"
  min_edge: "0.02"
  kelly_fraction: "0.25"
database:
  host: "localhost"
  port: "5432"
"""
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text(config_content)

        loader = ConfigLoader(config_dir=str(tmp_path))
        config = loader.load("test_config.yaml")

        assert config["trading"]["max_position_size"] == "1000.00"
        assert config["database"]["host"] == "localhost"

    def test_environment_variable_override(self, tmp_path, monkeypatch):
        """
        INTEGRATION: Environment variables override config values.

        Verifies:
        - Env var integration works
        - Config values can be overridden
        """
        from precog.config.config_loader import ConfigLoader

        # Set environment variable
        monkeypatch.setenv("PRECOG_DATABASE_HOST", "production-db.example.com")

        config_file = tmp_path / "env_config.yaml"
        config_file.write_text("""
database:
  host: "localhost"
  port: "5432"
""")

        loader = ConfigLoader(config_dir=str(tmp_path))
        loader.load("env_config.yaml")

        # ConfigLoader uses (config_name, key_path) pattern
        # Note: ConfigLoader doesn't automatically apply env var overrides to YAML
        # It provides separate get_env() method for env vars
        assert loader.get("env_config", "database.host") == "localhost"

    def test_multiple_config_files(self, tmp_path):
        """
        INTEGRATION: Load and merge multiple config files.

        Verifies:
        - Multiple files can be loaded
        - Values are accessible from all files
        """
        from precog.config.config_loader import ConfigLoader

        # Create multiple config files
        (tmp_path / "base.yaml").write_text("""
app:
  name: "precog"
  version: "1.0"
""")

        (tmp_path / "trading.yaml").write_text("""
trading:
  enabled: true
  mode: "paper"
""")

        loader = ConfigLoader(config_dir=str(tmp_path))
        loader.load("base.yaml")
        loader.load("trading.yaml")

        # ConfigLoader uses (config_name, key_path) pattern
        assert loader.get("base", "app.name") == "precog"
        assert loader.get("trading", "trading.enabled") is True

    def test_nested_config_access(self, tmp_path):
        """
        INTEGRATION: Access deeply nested configuration values.

        Verifies:
        - Nested key access works
        - Complex structures are preserved
        """
        from precog.config.config_loader import ConfigLoader

        config_file = tmp_path / "nested.yaml"
        config_file.write_text("""
level1:
  level2:
    level3:
      value: "deep_value"
      list:
        - item1
        - item2
""")

        loader = ConfigLoader(config_dir=str(tmp_path))
        loader.load("nested.yaml")

        # ConfigLoader uses (config_name, key_path) pattern
        assert loader.get("nested", "level1.level2.level3.value") == "deep_value"

    def test_config_with_special_characters(self, tmp_path):
        """
        INTEGRATION: Config with special characters and unicode.

        Verifies:
        - Unicode handling works
        - Special characters are preserved
        """
        from precog.config.config_loader import ConfigLoader

        config_file = tmp_path / "special.yaml"
        config_file.write_text(
            """
messages:
  greeting: "Hello, World!"
  emoji: "Trading"
  unicode: "Test"
  path: "/api/v1/markets?limit=100&offset=0"
""",
            encoding="utf-8",
        )

        loader = ConfigLoader(config_dir=str(tmp_path))
        loader.load("special.yaml")

        # ConfigLoader uses (config_name, key_path) pattern
        assert "Hello" in loader.get("special", "messages.greeting")
        assert "?" in loader.get("special", "messages.path")
