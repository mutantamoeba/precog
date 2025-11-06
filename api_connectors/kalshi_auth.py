"""
Kalshi API Authentication using RSA-PSS Signatures.

This module handles RSA-PSS signature generation for Kalshi API authentication.
Educational notes explain cryptography concepts for learning.

Why RSA-PSS?
------------
RSA-PSS is a digital signature scheme that provides:
1. Authentication: Proves you own the private key
2. Integrity: Ensures message hasn't been tampered with
3. Non-repudiation: You can't deny you made the request

How it works:
1. You create a message from: timestamp + method + path
2. You sign this message with your private key
3. Kalshi verifies with your public key (which they have)
4. If valid, they know it's really you making the request

Security properties:
- Even if someone intercepts your signature, they can't reuse it
  (because timestamp changes, making each signature unique)
- They can't create new valid signatures (because they don't have private key)
- Your private key never travels over the network

Reference: docs/api-integration/API_INTEGRATION_GUIDE_V2.0.md
Related ADR: ADR-047 (RSA-PSS Authentication Pattern)
"""

import time
import base64
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from cryptography.hazmat.backends import default_backend


def load_private_key(key_path: str) -> RSAPrivateKey:
    """
    Load RSA private key from PEM file.

    Args:
        key_path: Path to .pem file containing private key

    Returns:
        RSAPrivateKey object for signing

    Raises:
        FileNotFoundError: If key file doesn't exist
        ValueError: If file isn't a valid PEM private key

    Educational Note:
        PEM (Privacy Enhanced Mail) is a base64 encoding format for keys.
        It looks like:
        -----BEGIN PRIVATE KEY-----
        MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC...
        -----END PRIVATE KEY-----

        This is the private key. NEVER share this or commit to Git!

    Example:
        >>> private_key = load_private_key("./my_kalshi_key.pem")
        >>> # Now you can use private_key to sign requests
    """
    key_path_obj = Path(key_path)

    if not key_path_obj.exists():
        raise FileNotFoundError(
            f"Private key not found at: {key_path}\n"
            f"Please ensure your KALSHI_*_KEYFILE environment variable points to a valid .pem file."
        )

    try:
        with open(key_path_obj, "rb") as key_file:
            private_key = serialization.load_pem_private_key(
                key_file.read(),
                password=None,  # No password encryption (simpler, but less secure)
                backend=default_backend()
            )
    except Exception as e:
        raise ValueError(
            f"Failed to load private key from {key_path}. "
            f"Ensure the file is a valid PEM-formatted private key. Error: {e}"
        )

    return private_key


def generate_signature(
    private_key: RSAPrivateKey,
    timestamp: int,
    method: str,
    path: str
) -> str:
    """
    Generate RSA-PSS signature for Kalshi API request.

    Args:
        private_key: RSA private key (from load_private_key())
        timestamp: Current time in milliseconds since epoch
        method: HTTP method in UPPERCASE (GET, POST, DELETE, etc.)
        path: API endpoint path (e.g., '/trade-api/v2/markets')

    Returns:
        Base64-encoded signature string

    Example:
        >>> private_key = load_private_key("./my_key.pem")
        >>> timestamp = int(time.time() * 1000)
        >>> sig = generate_signature(
        ...     private_key=private_key,
        ...     timestamp=timestamp,
        ...     method="GET",
        ...     path="/trade-api/v2/markets"
        ... )
        >>> print(sig)  # Something like: "a8s7d6f5g4h3j2k1..."

    Educational Notes:
        1. Message construction:
           - Concatenate: timestamp + method + path
           - No delimiters, no spaces
           - Method MUST be uppercase

        2. PSS padding:
           - PSS = Probabilistic Signature Scheme
           - Adds randomness to signatures (same message = different signatures)
           - Makes signatures more secure against certain attacks
           - MGF1 = Mask Generation Function (used internally by PSS)

        3. SHA256 hashing:
           - Converts variable-length message to fixed 256-bit hash
           - One-way function (can't reverse hash to get message)
           - Tiny change in input = completely different hash output

        4. Base64 encoding:
           - Converts binary signature to ASCII text
           - Makes signature safe to send in HTTP headers
           - Adds ~33% to size but ensures compatibility

    Reference: Kalshi API documentation for signature format
    """
    # Step 1: Construct the message
    # Format: timestamp + METHOD + /path (no spaces, no delimiters)
    message = f"{timestamp}{method.upper()}{path}"

    # Step 2: Sign the message with RSA-PSS
    signature_bytes = private_key.sign(
        message.encode('utf-8'),  # Convert string to bytes
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),  # Mask generation function
            salt_length=padding.PSS.DIGEST_LENGTH  # 32 bytes for SHA256
        ),
        hashes.SHA256()  # Hash algorithm
    )

    # Step 3: Encode as base64 for HTTP transport
    signature_b64 = base64.b64encode(signature_bytes).decode('utf-8')

    return signature_b64


class KalshiAuth:
    """
    Manages Kalshi API authentication with RSA-PSS signatures.

    Handles:
    - Loading private keys
    - Generating signatures for requests
    - Building authentication headers
    - Token management (Kalshi tokens expire after 30 minutes)

    Usage:
        >>> auth = KalshiAuth(
        ...     api_key="your-key-id",
        ...     private_key_path="./your_key.pem"
        ... )
        >>>
        >>> headers = auth.get_headers(method="GET", path="/trade-api/v2/markets")
        >>> response = requests.get(url, headers=headers)

    Educational Note:
        The API key is like a username - it identifies you.
        The private key is like a password - it proves you're you.
        But unlike a password, the private key never gets sent!
        You just send signatures created WITH the private key.

    Reference: docs/api-integration/API_INTEGRATION_GUIDE_V2.0.md
    Related Requirements: REQ-API-002 (RSA-PSS Authentication)
    """

    def __init__(self, api_key: str, private_key_path: str):
        """
        Initialize authentication manager.

        Args:
            api_key: Your Kalshi API key (UUID format)
            private_key_path: Path to your .pem private key file

        Raises:
            FileNotFoundError: If private key file doesn't exist
            ValueError: If private key file is invalid

        Example:
            >>> auth = KalshiAuth(
            ...     api_key="a952bcbe-ec3b-4b5b-b8f9-11dae589608c",
            ...     private_key_path="./kalshi_demo_key.pem"
            ... )
        """
        self.api_key = api_key
        self.private_key = load_private_key(private_key_path)

        # Token management (Phase 1.5 - not implemented yet)
        # Kalshi tokens expire after 30 minutes
        self.token: Optional[str] = None
        self.token_expiry: Optional[int] = None

    def get_headers(self, method: str, path: str) -> dict:
        """
        Generate authentication headers for API request.

        Args:
            method: HTTP method (GET, POST, DELETE, etc.)
            path: API endpoint path (e.g., '/trade-api/v2/markets')

        Returns:
            Dictionary of headers to include in request

        Example:
            >>> auth = KalshiAuth("my-key", "./key.pem")
            >>> headers = auth.get_headers("GET", "/trade-api/v2/markets")
            >>> print(headers)
            {
                'KALSHI-ACCESS-KEY': 'my-key',
                'KALSHI-ACCESS-TIMESTAMP': '1729123456789',
                'KALSHI-ACCESS-SIGNATURE': 'a8s7d6f5g4h3j2k1...',
                'Content-Type': 'application/json'
            }

        Educational Note:
            These headers tell Kalshi:
            - WHO you are (KALSHI-ACCESS-KEY)
            - WHEN you made the request (KALSHI-ACCESS-TIMESTAMP)
            - PROOF it's really you (KALSHI-ACCESS-SIGNATURE)

            Kalshi verifies the signature using your public key they have on file.
            If signature is valid, they know:
            1. The request came from you (authentication)
            2. The request hasn't been tampered with (integrity)
            3. The request is recent (timestamp prevents replay attacks)
        """
        # Get current timestamp in milliseconds
        timestamp = int(time.time() * 1000)

        # Generate signature
        signature = generate_signature(
            private_key=self.private_key,
            timestamp=timestamp,
            method=method,
            path=path
        )

        # Build headers dictionary
        headers = {
            'KALSHI-ACCESS-KEY': self.api_key,
            'KALSHI-ACCESS-TIMESTAMP': str(timestamp),
            'KALSHI-ACCESS-SIGNATURE': signature,
            'Content-Type': 'application/json'
        }

        return headers

    def is_token_expired(self) -> bool:
        """
        Check if cached token is expired.

        Returns:
            True if token is expired or not set, False otherwise

        Note:
            Token management is planned for Phase 1.5.
            Currently, we generate new signatures for every request.
        """
        if self.token is None or self.token_expiry is None:
            return True

        current_time = int(time.time() * 1000)
        return current_time >= self.token_expiry

    def refresh_token(self) -> None:
        """
        Refresh authentication token.

        Kalshi tokens expire after 30 minutes. This method will:
        1. Generate a new signature
        2. Request a new token from Kalshi
        3. Cache the token for future requests

        Note:
            Token management is planned for Phase 1.5.
            Currently, we generate new signatures for every request,
            which is less efficient but simpler to implement.

        Related: REQ-API-002 (Token refresh every 30 minutes)
        """
        # Token refresh implementation deferred to Phase 1.5
        # For Phase 1, we generate fresh signatures for each request
        pass
