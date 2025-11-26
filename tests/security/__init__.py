"""
Security test suite for Precog trading system.

This package contains comprehensive security tests covering:
1. SQL injection resistance (parameterized queries)
2. Credential masking in logs (passwords, API keys, tokens)
3. Connection string sanitization (database errors)
4. API key rotation and token expiry

Related Issue: GitHub Issue #129 (Security Tests)
Related Pattern: Pattern 4 (Security - NO CREDENTIALS IN CODE)
Related Requirements: REQ-SEC-009 (SQL Injection Prevention, Credential Masking)
"""
