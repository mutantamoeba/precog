import re
import subprocess
from pathlib import Path


def find_secrets(files):
    secret_patterns = [
        r'api[_-]?key\s*=\s*[\'"][A-Za-z0-9_\-]{16,}[\'"]',
        r'token\s*=\s*[\'"][A-Za-z0-9_\-]{16,}[\'"]',
        r'password\s*=\s*[\'"][^\'"]+[\'"]',
    ]
    leaks = []
    for file in files:
        try:
            with Path(file).open(encoding="utf-8", errors="ignore") as f:
                for i, line in enumerate(f):
                    for pat in secret_patterns:
                        if re.search(pat, line, re.IGNORECASE):
                            leaks.append((file, i + 1, line.strip()))
        except Exception:
            continue
    return leaks


def check_postgres_encryption(config_files):
    results = []
    ssl_pat = re.compile(r'sslmode\s*=\s*[\'"]?disable[\'"]?', re.IGNORECASE)
    for cfg in config_files:
        try:
            with Path(cfg).open(encoding="utf-8", errors="ignore") as f:
                for i, line in enumerate(f):
                    if ssl_pat.search(line):
                        results.append((cfg, i + 1, line.strip()))
        except Exception:
            continue
    return results


def audit_dockerfiles():
    findings = []
    for path in Path().rglob("Dockerfile"):
        try:
            with path.open() as f:
                content = f.read()
                if "USER root" in content:
                    findings.append((path, "Runs as root user"))
                if "EXPOSE 5432" in content:
                    findings.append((path, "Exposes default Postgres port"))
                if not re.search(r"FROM\s+python:.*-slim", content):
                    findings.append((path, "Non-slim base image (increase attack surface)"))
        except Exception:
            continue
    return findings


def check_env_permissions():
    issues = []
    for env_path in Path().rglob(".env"):
        try:
            if env_path.stat().st_mode & 0o077:
                issues.append((str(env_path), "Potentially world-readable"))
        except Exception:
            continue
    return issues


def check_dependencies():
    vuln_report = []
    try:
        subprocess.run(["pip", "install", "--upgrade", "pip-audit"], check=True)
        result = subprocess.run(["pip-audit"], capture_output=True, text=True)
        if result.returncode != 0:
            vuln_report.append("Could not run pip-audit, check installation")
        else:
            for line in result.stdout.splitlines():
                if "Vulnerabilities" in line or "│" in line:
                    vuln_report.append(line)
    except Exception as e:
        vuln_report.append(str(e))
    return vuln_report


def main():
    print("Audit: Scanning for hardcoded secrets...")
    py_files = [str(p) for p in Path().rglob("*.py")]
    conf_files = [str(p) for p in Path().rglob("*.conf")]
    env_files = [str(p) for p in Path().rglob("*.env")]
    files = py_files + conf_files + env_files
    for file, line, val in find_secrets(files):
        print(f"[SECRET] {file}:{line} -> {val}")

    print("\nAudit: Checking PostgreSQL connection config for SSL enforcement...")
    pg_configs = [f for f in files if "postgres" in f or "database" in f]
    for cfg, line, val in check_postgres_encryption(pg_configs):
        print(f"[DB ENCRYPTION] {cfg}:{line} -> {val}")

    print("\nAudit: Scanning Dockerfile practices...")
    for finding in audit_dockerfiles():
        print(f"[DOCKER ISSUE] {finding[0]} -> {finding[1]}")

    print("\nAudit: Checking .env file permissions...")
    for env, issue in check_env_permissions():
        print(f"[ENV PERM] {env} -> {issue}")

    print("\nAudit: Dependency Vulnerability Scan...")
    for finding in check_dependencies():
        print(f"[DEPENDENCY] {finding}")


if __name__ == "__main__":
    main()
