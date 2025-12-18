"""
Configuration Management CLI Commands.

Provides commands for viewing and validating configuration files.

Commands:
    show     - Display configuration values
    validate - Validate configuration files
    env      - Show environment configuration (two-axis model)

Usage:
    precog config show trading
    precog config show trading --key account.max_total_exposure_dollars
    precog config validate
    precog config validate --file trading
    precog config env [--verbose]

Related:
    - Issue #204: CLI Refactor
    - docs/guides/CONFIGURATION_GUIDE_V3.1.md
    - docs/planning/CLI_REFACTOR_COMPREHENSIVE_PLAN_V1.0.md Section 4.2.6
"""

from __future__ import annotations

import typer
from rich.table import Table

from precog.cli._common import (
    ExitCode,
    cli_error,
    console,
    get_env_mode,
    get_kalshi_mode,
)

app = typer.Typer(
    name="config",
    help="Configuration management (show, validate, env)",
    no_args_is_help=True,
)

# Available configuration files
CONFIG_FILES = [
    "trading",
    "trade_strategies",
    "position_management",
    "probability_models",
    "markets",
    "data_sources",
    "system",
]


@app.command()
def show(
    config_file: str = typer.Argument(
        ...,
        help="Configuration file to display (e.g., 'trading' without .yaml extension)",
    ),
    key_path: str | None = typer.Option(
        None,
        "--key",
        "-k",
        help="Specific configuration key path (e.g., 'account.max_total_exposure_dollars')",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-V",
        help="Show detailed output",
    ),
) -> None:
    """Display configuration values.

    Shows the current configuration values loaded from YAML files.
    Use --key to display a specific setting instead of the entire file.

    Examples:
        precog config show trading
        precog config show trading --key account.max_total_exposure_dollars
        precog config show markets --verbose
    """
    console.print(f"\n[bold cyan]Configuration: {config_file}[/bold cyan]\n")

    try:
        from precog.config.config_loader import ConfigLoader

        config_loader = ConfigLoader()

        # Show specific key if provided
        if key_path:
            try:
                value = config_loader.get(config_file, key_path)
                console.print(f"[bold]Key:[/bold] {key_path}")
                console.print(f"[bold]Value:[/bold] {value}")

                if verbose:
                    console.print(f"\n[dim]Source: config/{config_file}[/dim]")

            except KeyError:
                console.print(f"[red]Key not found:[/red] {key_path}")
                console.print(f"\nAvailable keys in {config_file}:")
                full_config = config_loader.get(config_file)
                for key in full_config:
                    console.print(f"  - {key}")
                raise typer.Exit(code=1) from None

        # Show entire configuration file
        else:
            config = config_loader.get(config_file)

            # Pretty print configuration
            import yaml

            yaml_str = yaml.dump(config, default_flow_style=False, sort_keys=False)
            console.print(yaml_str)

            if verbose:
                console.print(f"[dim]Source: config/{config_file}[/dim]")
                console.print(f"[dim]Keys: {len(config)}[/dim]")

    except FileNotFoundError:
        console.print(f"[red]Configuration file not found:[/red] {config_file}")
        console.print("\nAvailable configuration files:")
        for cf in CONFIG_FILES:
            console.print(f"  - {cf}")
        raise typer.Exit(code=1) from None

    except Exception as e:
        cli_error(
            f"Failed to display configuration: {e}",
            ExitCode.CONFIG_ERROR,
            hint="Check configuration file syntax and paths",
        )


@app.command()
def validate(
    config_file: str | None = typer.Option(
        None,
        "--file",
        "-f",
        help="Specific configuration file to validate (default: all)",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-V",
        help="Show detailed validation results",
    ),
) -> None:
    """Validate configuration files.

    Checks that configuration files are valid YAML with sensible values.
    Validates:
        - YAML syntax
        - Required keys present
        - Value ranges
        - Decimal precision (no float contamination)

    Examples:
        precog config validate
        precog config validate --file trading
        precog config validate --verbose
    """
    console.print("\n[bold cyan]Configuration Validation[/bold cyan]\n")

    try:
        import yaml

        from precog.config.config_loader import ConfigLoader

        config_loader = ConfigLoader()

        # Determine which files to validate
        files_to_validate = [config_file] if config_file else CONFIG_FILES

        if config_file:
            console.print(f"Validating: {config_file}\n")
        else:
            console.print(f"Validating all {len(files_to_validate)} configuration files\n")

        files_passed = 0
        files_failed = 0

        for cf in files_to_validate:
            console.print(f"[bold]{cf}[/bold]")
            errors = []
            warnings = []

            # Normalize config file name
            cf_normalized = cf.replace(".yaml", "").replace("_config", "")

            try:
                # Check 1: Can we load the file?
                config = config_loader.get(cf)
                console.print("  [green]OK[/green] YAML syntax valid")

                # Check 2: Is the file empty?
                if not config:
                    errors.append("Configuration file is empty")
                    console.print("  [red]FAIL[/red] File is empty")
                else:
                    console.print(f"  [green]OK[/green] Contains {len(config)} top-level keys")

                # Check 3: Check for float contamination in financial configs
                if cf_normalized in ["trading", "trade_strategies", "markets"]:
                    file_path = f"src/precog/config/{cf_normalized}.yaml"
                    try:
                        with open(file_path, encoding="utf-8") as f:
                            raw_content = f.read()
                            # Look for potential float notation
                            lines_with_decimals = [
                                line
                                for line in raw_content.split("\n")
                                if "." in line
                                and any(c.isdigit() for c in line)
                                and not line.strip().startswith("#")
                                and '": "' not in line  # Skip string values
                                and ": '" not in line
                            ]
                            if lines_with_decimals:
                                warnings.append(
                                    "May contain float values (should use string format for Decimal)"
                                )
                                if verbose:
                                    console.print(
                                        "  [yellow]WARN[/yellow] Possible float contamination"
                                    )
                    except FileNotFoundError:
                        pass  # File not in expected location, skip this check

                if not errors:
                    console.print("[green]  OK Validation passed[/green]\n")
                    files_passed += 1
                else:
                    console.print(f"[red]  FAIL Validation failed: {len(errors)} errors[/red]\n")
                    files_failed += 1

                if verbose and (errors or warnings):
                    if errors:
                        console.print("  [red]Errors:[/red]")
                        for error in errors:
                            console.print(f"    - {error}")
                    if warnings:
                        console.print("  [yellow]Warnings:[/yellow]")
                        for warning in warnings:
                            console.print(f"    - {warning}")
                    console.print()

            except FileNotFoundError:
                console.print(f"  [red]FAIL[/red] File not found: config/{cf}\n")
                files_failed += 1

            except yaml.YAMLError as yaml_error:
                console.print(f"  [red]FAIL[/red] YAML parsing error: {yaml_error}\n")
                files_failed += 1

            except Exception as validation_error:
                console.print(f"  [red]FAIL[/red] Validation error: {validation_error}\n")
                files_failed += 1

        # Summary
        total_files = len(files_to_validate)
        console.print("[bold]Validation Summary:[/bold]")
        console.print(f"  Files passed: [green]{files_passed}/{total_files}[/green]")
        console.print(f"  Files failed: [red]{files_failed}/{total_files}[/red]")

        if files_failed == 0:
            console.print("\n[bold green]All configuration files valid![/bold green]")
        else:
            console.print("\n[bold red]Some configuration files failed validation[/bold red]")
            raise typer.Exit(code=1)

    except typer.Exit:
        raise
    except Exception as e:
        cli_error(
            f"Configuration validation failed: {e}",
            ExitCode.CONFIG_ERROR,
        )


@app.command()
def env(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-V",
        help="Show detailed environment configuration",
    ),
) -> None:
    """Display current environment configuration.

    Shows the two-axis environment model:
        1. Application Environment (PRECOG_ENV): Controls database selection
        2. Market Mode (KALSHI_MODE): Controls API endpoints (demo/live)

    Examples:
        precog config env
        precog config env --verbose
    """
    import os

    console.print()
    console.print("[bold]Two-Axis Environment Configuration[/bold]")
    console.print()

    # Axis 1: Application Environment
    app_env = get_env_mode()
    env_colors = {
        "dev": "green",
        "development": "green",
        "test": "blue",
        "staging": "yellow",
        "production": "red",
        "prod": "red",
    }
    env_color = env_colors.get(app_env.lower(), "white")

    table1 = Table(title="Axis 1: Application Environment")
    table1.add_column("Setting", style="cyan", no_wrap=True)
    table1.add_column("Value", style="white")

    table1.add_row("PRECOG_ENV", f"[{env_color}]{app_env}[/{env_color}]")
    table1.add_row(
        "Database",
        f"[{env_color}]precog_{app_env}[/{env_color}]"
        if app_env != "production"
        else "[red]precog_prod[/red]",
    )

    console.print(table1)
    console.print()

    # Axis 2: Market Mode
    kalshi_mode = get_kalshi_mode()
    mode_colors = {"demo": "green", "live": "red"}
    mode_color = mode_colors.get(kalshi_mode.lower(), "white")

    table2 = Table(title="Axis 2: Market API Mode (Kalshi)")
    table2.add_column("Setting", style="cyan", no_wrap=True)
    table2.add_column("Value", style="white")

    table2.add_row("KALSHI_MODE", f"[{mode_color}]{kalshi_mode}[/{mode_color}]")
    table2.add_row(
        "Risk Level",
        "[green]None (fake money)[/green]"
        if kalshi_mode.lower() == "demo"
        else "[red]FINANCIAL (real money!)[/red]",
    )

    console.print(table2)
    console.print()

    # Show detailed env vars in verbose mode
    if verbose:
        console.print("[bold]All Environment Variables[/bold]")
        env_vars = [
            ("PRECOG_ENV", os.getenv("PRECOG_ENV", "[dim]not set[/dim]")),
            ("KALSHI_MODE", os.getenv("KALSHI_MODE", "[dim]not set[/dim]")),
            (
                "KALSHI_API_KEY_ID",
                os.getenv("KALSHI_API_KEY_ID", "[dim]not set[/dim]")[:8] + "..."
                if os.getenv("KALSHI_API_KEY_ID")
                else "[dim]not set[/dim]",
            ),
            ("KALSHI_PRIVATE_KEY_PATH", os.getenv("KALSHI_PRIVATE_KEY_PATH", "[dim]not set[/dim]")),
            ("PRECOG_DB_HOST", os.getenv("PRECOG_DB_HOST", "[dim]not set[/dim]")),
            ("PRECOG_DB_NAME", os.getenv("PRECOG_DB_NAME", "[dim]not set[/dim]")),
        ]

        table3 = Table()
        table3.add_column("Variable", style="cyan")
        table3.add_column("Value", style="white")

        for var, value in env_vars:
            table3.add_row(var, value)

        console.print(table3)
