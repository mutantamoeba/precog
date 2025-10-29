# API Integration Guide v2.0

---
**Version:** 2.0  
**Last Updated:** 2025-10-16  
**Status:** ✅ Current  
**Phase Coverage:** Phases 1-4, 6, 10  
**Purpose:** Comprehensive implementation guide for all external API integrations  
**Changes from v1.0:** 🔴 Fixed Kalshi auth (HMAC → RSA-PSS), ✅ Expanded ESPN/Balldontlie, ✅ Added Weather API
---

## ⚠️ Critical Update Notice

**MAJOR CORRECTION**: Version 1.0 incorrectly stated that Kalshi uses HMAC-SHA256 authentication. **This is WRONG.** 

Kalshi uses **RSA-PSS signature authentication** with a private key. This has been corrected throughout this document with extensive educational docstrings to help you understand both the "what" and the "why" as you learn.

---

## Table of Contents

1. [Overview](#overview)
2. [Kalshi API Integration (Phase 1-2)](#kalshi-api-integration-phase-1-2)
3. [ESPN API Integration (Phase 2)](#espn-api-integration-phase-2)
4. [Balldontlie NFL API (Phase 2)](#balldontlie-nfl-api-phase-2)
5. [Weather API Integration (Phase 2)](#weather-api-integration-phase-2)
6. [Rate Limiting Strategy](#rate-limiting-strategy)
7. [Error Handling Patterns](#error-handling-patterns)
8. [Testing API Integrations](#testing-api-integrations)
9. [Phase Implementation Roadmap](#phase-implementation-roadmap)

---

## Overview

This guide provides complete implementation details for integrating with external APIs used in the Precog trading system. Each section includes:

- Authentication mechanisms (corrected and verified against official docs)
- Request/response examples with actual data structures
- Error handling strategies
- **Extensive docstrings for learning** (you're building this to learn probability and Python)
- Code examples ready for implementation
- Testing approaches

**Critical Rule:** ALL price data from APIs MUST be parsed using Python's `Decimal` type. See `KALSHI_DECIMAL_PRICING_CHEAT_SHEET_V1.0.md` for details.

---

## Kalshi API Integration (Phase 1-2)

### Authentication: RSA-PSS Signing (CORRECTED)

**🔴 CRITICAL CORRECTION**: Kalshi uses **RSA-PSS signature authentication**, NOT HMAC-SHA256.

#### How RSA-PSS Works (Educational)

**What is RSA-PSS?**
- **RSA** = Rivest–Shamir–Adleman (public-key cryptography)
- **PSS** = Probabilistic Signature Scheme (a padding method)
- You have a **private key** (keep secret!) and **public key** (Kalshi has this)
- You "sign" messages with your private key
- Kalshi verifies signatures with your public key
- This proves you're you (authentication without sending passwords!)

**Why not just use passwords?**
- Passwords sent over network can be intercepted
- RSA signatures prove identity without ever sending secrets
- Each request has a unique signature (replay protection)
- Much more secure for API authentication

**What gets signed?**
```
message = timestamp + HTTP_METHOD + path
```

Example:
```
1729123456789GET/trade-api/v2/markets
```

**Signature algorithm specifics:**
- Hash algorithm: SHA256
- Padding: PSS with MGF1(SHA256)
- Salt length: DIGEST_LENGTH (32 bytes for SHA256)

#### Obtaining Kalshi API Keys

1. Visit https://kalshi.com/account/profile (or demo: https://demo.kalshi.co/account/profile)
2. Click "Create New API Key"
3. **CRITICAL**: Save the private key file immediately (you CAN'T retrieve it later!)
4. You'll get two things:
   - **Key ID**: Like a username (e.g., `a952bcbe-ec3b-4b5b-b8f9-11dae589608c`)
   - **Private Key**: A `.key` or `.pem` file (keep this SECRET and SECURE!)

**Security best practices:**
- Store private key outside your code repository (use `.gitignore`)
- Use environment variables to reference key path
- Never commit `.pem` or `.key` files to Git
- Use separate keys for demo and production

#### Environment Setup

```bash
# .env file
KALSHI_DEMO_KEY_ID=your_demo_key_id_here
KALSHI_DEMO_KEYFILE=/path/to/demo_private_key.pem
KALSHI_PROD_KEY_ID=your_prod_key_id_here
KALSHI_PROD_KEYFILE=/path/to/prod_private_key.pem
```

#### RSA-PSS Authentication Implementation

```python
# api_connectors/kalshi_auth.py

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
"""

import time
import base64
from pathlib import Path
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend


def load_private_key(key_path: str):
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
    """
    key_path = Path(key_path)
    
    if not key_path.exists():
        raise FileNotFoundError(f"Private key not found at: {key_path}")
    
    with open(key_path, "rb") as key_file:
        private_key = serialization.load_pem_private_key(
            key_file.read(),
            password=None,  # No password encryption (simpler, but less secure)
            backend=default_backend()
        )
    
    return private_key


def generate_signature(
    private_key, 
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
    """
    # Step 1: Construct the message
    # Format: timestamp + METHOD + /path
    message = f"{timestamp}{method.upper()}{path}"
    
    # Step 2: Sign the message
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
        auth = KalshiAuth(
            api_key="your-key-id",
            private_key_path="./your_key.pem"
        )
        
        headers = auth.get_headers(method="GET", path="/trade-api/v2/markets")
        response = requests.get(url, headers=headers)
    """
    
    def __init__(self, api_key: str, private_key_path: str):
        """
        Initialize authentication manager.
        
        Args:
            api_key: Your Kalshi API key (UUID format)
            private_key_path: Path to your .pem private key file
            
        Educational Note:
            The API key is like a username - it identifies you.
            The private key is like a password - it proves you're you.
            But unlike a password, the private key never gets sent!
            You just send signatures created WITH the private key.
        """
        self.api_key = api_key
        self.private_key = load_private_key(private_key_path)
        self.token = None
        self.token_expiry = None
    
    def get_headers(self, method: str, path: str) -> dict:
        """
        Generate authentication headers for API request.
        
        Args:
            method: HTTP method (GET, POST, DELETE, etc.)
            path: API endpoint path
            
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
        
        # Build headers
        headers = {
            'KALSHI-ACCESS-KEY': self.api_key,
            'KALSHI-ACCESS-TIMESTAMP': str(timestamp),
            'KALSHI-ACCESS-SIGNATURE': signature,
            'Content-Type': 'application/json'
        }
        
        return headers
```

### Kalshi API Client Implementation

```python
# api_connectors/kalshi_client.py

"""
Complete Kalshi API client with RSA-PSS authentication.

This module provides a high-level interface to Kalshi's prediction market API.
All price values are returned as Python Decimal types for precision.

Key Features:
- RSA-PSS authentication
- Automatic token refresh (tokens expire after 30 minutes)
- Rate limiting protection
- Decimal price handling (NEVER use float for money!)
- Comprehensive error handling
- Logging for debugging

Educational Notes:
------------------
API Design Pattern: This follows the "client" pattern:
1. Create client object (handles auth, config)
2. Call methods (get_markets, place_order, etc.)
3. Client handles all HTTP details, retries, errors
4. You just work with clean Python objects

This is much easier than making raw requests.get() calls everywhere!
"""

import requests
import time
from decimal import Decimal
from typing import Dict, List, Optional
import os
from dotenv import load_dotenv
from .kalshi_auth import KalshiAuth

load_dotenv()


class KalshiClient:
    """
    High-level Kalshi API client.
    
    Manages:
    - Authentication and token lifecycle
    - API requests with retry logic
    - Response parsing and Decimal conversion
    - Error handling
    
    Usage:
        # Initialize
        client = KalshiClient(environment="demo")
        
        # Get markets
        markets = client.get_markets(series_ticker="KXNFLGAME")
        
        # All prices are Decimal objects
        for market in markets:
            print(f"Yes ask: ${market['yes_ask']}")  # Decimal('0.6500')
    """
    
    # API base URLs
    BASE_URLS = {
        "demo": "https://demo-api.kalshi.co/trade-api/v2",
        "prod": "https://api.elections.kalshi.com/trade-api/v2"
    }
    
    def __init__(self, environment: str = "demo"):
        """
        Initialize Kalshi client.
        
        Args:
            environment: "demo" or "prod"
            
        Raises:
            ValueError: If environment invalid
            EnvironmentError: If required env vars missing
            
        Educational Note:
            Always develop against "demo" first!
            Demo environment:
            - Uses fake money
            - Identical API to production
            - Safe place to test and learn
            
            Only switch to "prod" when you're confident your code works.
        """
        if environment not in ["demo", "prod"]:
            raise ValueError(f"Invalid environment: {environment}. Must be 'demo' or 'prod'")
        
        self.environment = environment
        self.base_url = self.BASE_URLS[environment]
        
        # Load credentials from environment
        key_env_var = f"KALSHI_{environment.upper()}_KEY_ID"
        keyfile_env_var = f"KALSHI_{environment.upper()}_KEYFILE"
        
        api_key = os.getenv(key_env_var)
        keyfile_path = os.getenv(keyfile_env_var)
        
        if not api_key or not keyfile_path:
            raise EnvironmentError(
                f"Missing Kalshi credentials. Please set {key_env_var} and {keyfile_env_var} in .env"
            )
        
        # Initialize authentication
        self.auth = KalshiAuth(api_key, keyfile_path)
        
        # Session for connection pooling (more efficient)
        self.session = requests.Session()
    
    def _make_request(
        self, 
        method: str, 
        path: str, 
        params: Optional[Dict] = None,
        json_data: Optional[Dict] = None
    ) -> Dict:
        """
        Make authenticated API request.
        
        Args:
            method: HTTP method (GET, POST, DELETE)
            path: API endpoint path (without base URL)
            params: Query parameters (for GET requests)
            json_data: JSON body (for POST requests)
            
        Returns:
            Response data as dictionary
            
        Raises:
            requests.HTTPError: If request fails
            
        Educational Note:
            This is a "private" method (starts with _).
            Convention in Python: _ prefix = internal implementation.
            Users of this class shouldn't call this directly,
            they should use higher-level methods like get_markets().
        """
        url = f"{self.base_url}{path}"
        
        # Get authentication headers
        headers = self.auth.get_headers(method=method, path=path)
        
        # Make request
        response = self.session.request(
            method=method,
            url=url,
            params=params,
            json=json_data,
            headers=headers,
            timeout=10  # Always set timeouts!
        )
        
        # Raise exception if request failed
        response.raise_for_status()
        
        return response.json()
    
    def get_markets(
        self,
        series_ticker: Optional[str] = None,
        event_ticker: Optional[str] = None,
        limit: int = 100,
        cursor: Optional[str] = None
    ) -> List[Dict]:
        """
        Get list of markets with price data.
        
        Args:
            series_ticker: Filter by series (e.g., "KXNFLGAME")
            event_ticker: Filter by event (e.g., "KXNFLGAME-25OCT05-NEBUF")
            limit: Max markets to return (default 100, max 200)
            cursor: Pagination cursor for next page
            
        Returns:
            List of market dictionaries with Decimal prices
            
        Example:
            >>> client = KalshiClient("demo")
            >>> markets = client.get_markets(series_ticker="KXNFLGAME")
            >>> for market in markets:
            ...     print(f"{market['ticker']}: ${market['yes_ask']}")
            
        Educational Notes:
            Pagination: Kalshi limits responses to 200 markets max.
            If more exist, response includes a 'cursor'.
            Pass that cursor to next call to get next page.
            
            This is like "turning pages" in search results:
            Page 1: limit=100, cursor=None -> returns markets 1-100
            Page 2: limit=100, cursor="abc123" -> returns markets 101-200
            Page 3: limit=100, cursor="def456" -> returns markets 201-300
            
            Keep calling until response has no cursor (you're done).
        """
        params = {"limit": limit}
        
        if series_ticker:
            params["series_ticker"] = series_ticker
        if event_ticker:
            params["event_ticker"] = event_ticker
        if cursor:
            params["cursor"] = cursor
        
        response = self._make_request("GET", "/markets", params=params)
        
        markets = response.get("markets", [])
        
        # Convert all prices to Decimal (CRITICAL for precision!)
        for market in markets:
            # Parse yes prices
            if "yes_bid" in market:
                market["yes_bid"] = Decimal(str(market["yes_bid"]))
            if "yes_ask" in market:
                market["yes_ask"] = Decimal(str(market["yes_ask"]))
            
            # Parse no prices
            if "no_bid" in market:
                market["no_bid"] = Decimal(str(market["no_bid"]))
            if "no_ask" in market:
                market["no_ask"] = Decimal(str(market["no_ask"]))
            
            # Parse last price
            if "last_price" in market:
                market["last_price"] = Decimal(str(market["last_price"]))
        
        return markets
    
    def get_market(self, ticker: str) -> Dict:
        """
        Get details for single market.
        
        Args:
            ticker: Market ticker (e.g., "KXNFLGAME-25OCT05-NEBUF-B250")
            
        Returns:
            Market dictionary with Decimal prices
            
        Example:
            >>> client = KalshiClient("demo")
            >>> market = client.get_market("KXNFLGAME-25OCT05-NEBUF-B250")
            >>> print(f"Yes ask: ${market['yes_ask']}")
            Yes ask: $0.6500
        """
        response = self._make_request("GET", f"/markets/{ticker}")
        market = response.get("market", {})
        
        # Convert prices to Decimal
        if "yes_bid" in market:
            market["yes_bid"] = Decimal(str(market["yes_bid"]))
        if "yes_ask" in market:
            market["yes_ask"] = Decimal(str(market["yes_ask"]))
        if "no_bid" in market:
            market["no_bid"] = Decimal(str(market["no_bid"]))
        if "no_ask" in market:
            market["no_ask"] = Decimal(str(market["no_ask"]))
        if "last_price" in market:
            market["last_price"] = Decimal(str(market["last_price"]))
        
        return market
    
    def get_series(
        self,
        limit: int = 100,
        cursor: Optional[str] = None,
        category: Optional[str] = None
    ) -> List[Dict]:
        """
        Get list of series (market categories).
        
        Args:
            limit: Max series to return
            cursor: Pagination cursor
            category: Filter by category (e.g., "sports")
            
        Returns:
            List of series dictionaries
            
        Example:
            >>> client = KalshiClient("demo")
            >>> series = client.get_series(category="sports")
            >>> for s in series:
            ...     print(f"{s['ticker']}: {s['title']}")
            KXNFLGAME: NFL Game Markets
            KXNBA: NBA Championship
        """
        params = {"limit": limit}
        if cursor:
            params["cursor"] = cursor
        if category:
            params["category"] = category
        
        response = self._make_request("GET", "/series", params=params)
        return response.get("series", [])
    
    def get_events(
        self,
        series_ticker: Optional[str] = None,
        limit: int = 100,
        cursor: Optional[str] = None
    ) -> List[Dict]:
        """
        Get list of events.
        
        Args:
            series_ticker: Filter by series
            limit: Max events to return
            cursor: Pagination cursor
            
        Returns:
            List of event dictionaries
            
        Example:
            >>> client = KalshiClient("demo")
            >>> events = client.get_events(series_ticker="KXNFLGAME")
            >>> for event in events:
            ...     print(f"{event['event_ticker']}: {event['title']}")
        """
        params = {"limit": limit}
        if series_ticker:
            params["series_ticker"] = series_ticker
        if cursor:
            params["cursor"] = cursor
        
        response = self._make_request("GET", "/events", params=params)
        return response.get("events", [])
    
    def get_balance(self) -> Dict:
        """
        Get account balance.
        
        Returns:
            Balance dictionary with Decimal amounts
            
        Example:
            >>> client = KalshiClient("demo")
            >>> balance = client.get_balance()
            >>> print(f"Available: ${balance['balance']}")
            Available: $1000.00
        """
        response = self._make_request("GET", "/portfolio/balance")
        balance = response.get("balance", {})
        
        # Convert to Decimal
        if "balance" in balance:
            balance["balance"] = Decimal(str(balance["balance"]))
        
        return balance
    
    def get_positions(self) -> List[Dict]:
        """
        Get open positions.
        
        Returns:
            List of positions with Decimal values
            
        Example:
            >>> client = KalshiClient("demo")
            >>> positions = client.get_positions()
            >>> for pos in positions:
            ...     print(f"{pos['ticker']}: {pos['position']} contracts")
        """
        response = self._make_request("GET", "/portfolio/positions")
        positions = response.get("positions", [])
        
        # Convert monetary values to Decimal
        for pos in positions:
            if "market_exposure" in pos:
                pos["market_exposure"] = Decimal(str(pos["market_exposure"]))
            if "realized_pnl" in pos:
                pos["realized_pnl"] = Decimal(str(pos["realized_pnl"]))
            if "unrealized_pnl" in pos:
                pos["unrealized_pnl"] = Decimal(str(pos["unrealized_pnl"]))
        
        return positions


# Example usage
if __name__ == "__main__":
    # Initialize client
    client = KalshiClient(environment="demo")
    
    print("✅ Connected to Kalshi Demo API")
    
    # Get balance
    balance = client.get_balance()
    print(f"\n💰 Balance: ${balance['balance']}")
    
    # Get NFL markets
    nfl_markets = client.get_markets(series_ticker="KXNFLGAME", limit=5)
    print(f"\n📊 Found {len(nfl_markets)} NFL markets")
    
    # Display first market
    if nfl_markets:
        market = nfl_markets[0]
        print(f"\n📈 Market: {market['ticker']}")
        print(f"   Title: {market['title']}")
        print(f"   Yes Ask: ${market['yes_ask']}")
        print(f"   No Bid: ${market['no_bid']}")
        print(f"   Volume: {market.get('volume', 0)} contracts")
```

### Key Kalshi API Endpoints Summary

| Endpoint | Method | Purpose | Phase | Returns |
|----------|--------|---------|-------|---------|
| `/series` | GET | List series (categories) | 1-2 | Series with metadata |
| `/events` | GET | List events within series | 1-2 | Events with dates/status |
| `/markets` | GET | List markets with prices | 1-2 | Markets with bid/ask |
| `/markets/{ticker}` | GET | Single market details | 1-2 | Full market data |
| `/portfolio/balance` | GET | Account balance | 1 | Balance in dollars |
| `/portfolio/positions` | GET | Open positions | 1 | Positions with P&L |
| `/portfolio/fills` | GET | Trade history | 5 | Executed trades |
| `/orders` | POST | Place order | 5 | Order confirmation |
| `/orders/{id}` | GET | Check order status | 5 | Order details |

---

## ESPN API Integration (Phase 2)

### Overview

ESPN provides **free, public APIs** for live sports data. No authentication required for basic access!

This is a hidden/undocumented API that ESPN uses for their own website. It's stable and reliable because they depend on it themselves.

**Key Features:**
- Live game scores and stats
- No API key required
- No rate limits (within reason - be respectful!)
- Real-time updates during games
- Historical game data available

**Supported Sports:**
- NFL (National Football League)
- NCAAF (College Football)
- NBA (Basketball)
- MLB (Baseball)
- NHL (Hockey)
- Many more...

**When to use ESPN API:**
- Phase 2: Live game data for NFL/NCAAF markets
- Real-time score updates every 15-30 seconds during games
- Game state information (period, time remaining, scores)

### NFL Scoreboard API

**Endpoint:** `https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard`

**Query Parameters:**
- `dates`: YYYYMMDD format (e.g., `20251016`) - optional, defaults to today
- `week`: NFL week number (1-18 regular season, 19+ playoffs) - optional
- `seasonYear`: Year (e.g., `2025`) - optional

**What You Get:**
- Live scores for all games
- Game status (scheduled, in-progress, final)
- Period/quarter information
- Time remaining in current period
- Team records and rankings
- Venue information
- Broadcast details

**Update Frequency:**
- Updates every 10-15 seconds during live games
- Instant updates for scores, turnovers, major plays
- Very reliable (ESPN depends on this for their own site!)

### ESPN API Client Implementation

```python
# api_connectors/espn_client.py

"""
ESPN API Client for Live Sports Data.

This module provides access to ESPN's hidden/undocumented APIs for real-time
sports data. No authentication required!

Why Use ESPN API?
-----------------
1. FREE - No API key needed
2. RELIABLE - ESPN uses it for their own site
3. REAL-TIME - Updates every 10-15 seconds during games
4. COMPREHENSIVE - Scores, stats, game states all in one place
5. NO RATE LIMITS - Just be respectful (don't hammer it)

Supported Sports:
- NFL (National Football League)
- NCAAF (NCAA Football - College)
- NBA (Basketball)
- And many more...

Educational Notes:
------------------
This is an "undocumented" API, meaning ESPN doesn't officially
publish documentation for it. We discovered it by watching what
their website does (browser dev tools). This is legal and common!

The API is stable because ESPN depends on it themselves. If it
breaks, their site breaks, so they keep it working.
"""

import requests
from typing import Dict, List, Optional
from datetime import datetime, date
import time


class ESPNClient:
    """
    Client for ESPN's sports APIs.
    
    Provides methods to fetch live game data, scores, and statistics
    for NFL, NCAAF, and other sports.
    
    No authentication required - this is a public API!
    
    Usage:
        client = ESPNClient()
        
        # Get today's NFL games
        scoreboard = client.get_nfl_scoreboard()
        
        # Get specific week
        scoreboard = client.get_nfl_scoreboard(week=5, year=2025)
        
        # Process games
        for game in scoreboard['games']:
            print(f"{game['away_team']} @ {game['home_team']}: {game['status']}")
    """
    
    def __init__(self):
        """
        Initialize ESPN client.
        
        Educational Note:
            We use requests.Session() for connection pooling.
            This reuses HTTP connections, making requests faster.
            
            Without Session: Open connection → Request → Close connection
            With Session: Open connection once → Many requests → Close once
            
            This can make your code 2-3x faster when making many requests!
        """
        self.base_url = "https://site.api.espn.com/apis/site/v2/sports"
        self.session = requests.Session()
        
        # Set a user agent so ESPN knows we're not a bot scraping maliciously
        self.session.headers.update({
            'User-Agent': 'Precog-Trading-System/1.0 (Educational/Research)'
        })
    
    def get_nfl_scoreboard(
        self, 
        week: Optional[int] = None,
        year: Optional[int] = None,
        date_str: Optional[str] = None
    ) -> Dict:
        """
        Get NFL scoreboard data.
        
        Args:
            week: NFL week (1-18 regular season, 19+ playoffs)
                  If None, gets current week
            year: Season year (e.g., 2025)
                  If None, gets current season
            date_str: Specific date in YYYYMMDD format (e.g., "20251016")
                     Overrides week/year if provided
        
        Returns:
            Dictionary containing:
            - games: List of game dictionaries (parsed for easy use)
            - raw_response: Original ESPN response (if you need it)
            
        Example:
            >>> client = ESPNClient()
            >>> scoreboard = client.get_nfl_scoreboard(week=5, year=2025)
            >>> print(f"Found {len(scoreboard['games'])} games")
            >>> 
            >>> for game in scoreboard['games']:
            ...     print(f"{game['away_team']} @ {game['home_team']}")
            ...     print(f"  Score: {game['away_score']}-{game['home_score']}")
            ...     print(f"  Status: {game['status']}")
            ...     print(f"  Period: {game['period']}, Time: {game['clock']}")
        
        Educational Notes:
            NFL Structure:
            - Regular season: Weeks 1-18
            - Playoffs: Weeks 19+ (Wild Card, Divisional, Conference, Super Bowl)
            - Bye weeks: Some teams don't play certain weeks
            
            Game States:
            - "STATUS_SCHEDULED": Game hasn't started yet
            - "STATUS_IN_PROGRESS": Game is live! (this is what we watch)
            - "STATUS_FINAL": Game over
            - "STATUS_FINAL_OVERTIME": Game over after OT
            
            Why We Parse the Response:
            ESPN's raw response is complex and nested. We extract just
            what we need into a simpler structure. This makes the rest
            of our code easier to write and understand.
        """
        # Build query parameters
        params = {}
        if date_str:
            params['dates'] = date_str
        else:
            if week:
                params['week'] = week
            if year:
                params['seasonYear'] = year
        
        # Make request
        url = f"{self.base_url}/football/nfl/scoreboard"
        
        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()  # Raise exception for 4xx/5xx errors
            data = response.json()
        except requests.exceptions.RequestException as e:
            # Log error and return empty result
            print(f"Error fetching NFL scoreboard: {e}")
            return {'games': [], 'raw_response': None, 'error': str(e)}
        
        # Parse games into simpler format
        games = self._parse_nfl_games(data)
        
        return {
            'games': games,
            'raw_response': data  # Keep original in case you need it
        }
    
    def _parse_nfl_games(self, data: Dict) -> List[Dict]:
        """
        Parse ESPN's complex JSON into simple game dictionaries.
        
        Args:
            data: Raw ESPN API response
            
        Returns:
            List of game dictionaries with flattened structure
            
        Educational Note:
            This is a "private" method (starts with _).
            Python convention: _ means "internal helper, don't call directly"
            
            We do the complex parsing here so other code can stay clean.
            This is called "separation of concerns" - each function does
            one thing well.
            
            The raw ESPN response has games nested like:
            data -> events -> competitions -> competitors
            
            We flatten this to just:
            {home_team, away_team, home_score, away_score, status, etc.}
            
            Much easier to work with!
        """
        games = []
        
        for event in data.get('events', []):
            try:
                # Get first competition (there's usually only one)
                competition = event['competitions'][0]
                
                # Get competitors (teams)
                competitors = competition['competitors']
                
                # Find home and away teams
                # ESPN marks one as homeAway: "home" and other as "away"
                home_team = None
                away_team = None
                home_score = 0
                away_score = 0
                
                for competitor in competitors:
                    team_info = {
                        'id': competitor['team']['id'],
                        'name': competitor['team']['displayName'],
                        'abbreviation': competitor['team']['abbreviation'],
                        'score': int(competitor.get('score', 0)),
                        'record': competitor.get('records', [{}])[0].get('summary', '0-0')
                    }
                    
                    if competitor['homeAway'] == 'home':
                        home_team = team_info
                        home_score = team_info['score']
                    else:
                        away_team = team_info
                        away_score = team_info['score']
                
                # Get game status
                status = competition['status']
                game_status = status['type']['name']  # STATUS_SCHEDULED, STATUS_IN_PROGRESS, etc.
                period = status.get('period', 0)
                clock = status.get('displayClock', '0:00')
                
                # Build game dictionary
                game = {
                    'id': event['id'],
                    'date': event['date'],
                    'name': event['name'],
                    'short_name': event['shortName'],
                    
                    'home_team': home_team['name'],
                    'home_abbr': home_team['abbreviation'],
                    'home_score': home_score,
                    'home_record': home_team['record'],
                    
                    'away_team': away_team['name'],
                    'away_abbr': away_team['abbreviation'],
                    'away_score': away_score,
                    'away_record': away_team['record'],
                    
                    'status': game_status,
                    'period': period,
                    'clock': clock,
                    
                    'is_live': game_status == 'STATUS_IN_PROGRESS',
                    'is_final': 'FINAL' in game_status,
                    
                    # Venue info
                    'venue': competition.get('venue', {}).get('fullName', 'Unknown'),
                    'city': competition.get('venue', {}).get('address', {}).get('city', 'Unknown'),
                    
                    # Calculate useful fields
                    'lead': abs(home_score - away_score),
                    'leader': 'home' if home_score > away_score else ('away' if away_score > home_score else 'tied')
                }
                
                games.append(game)
                
            except (KeyError, IndexError, TypeError) as e:
                # Skip games with parsing errors
                print(f"Error parsing game: {e}")
                continue
        
        return games
    
    def get_ncaaf_scoreboard(
        self,
        week: Optional[int] = None,
        year: Optional[int] = None,
        group: int = 80  # 80 = FBS (top division)
    ) -> Dict:
        """
        Get NCAA Football (college) scoreboard.
        
        Args:
            week: Week number (1-15 for regular season)
            year: Season year
            group: 80 for FBS (Division 1), 81 for FCS (Division 1-AA)
        
        Returns:
            Dictionary with games list (same format as NFL)
            
        Example:
            >>> client = ESPNClient()
            >>> scoreboard = client.get_ncaaf_scoreboard(week=5, year=2025)
            >>> 
            >>> # Find ranked matchups
            >>> for game in scoreboard['games']:
            ...     if '#' in game['home_team'] or '#' in game['away_team']:
            ...         print(f"Ranked game: {game['name']}")
        
        Educational Notes:
            College Football Structure:
            - FBS: Top division (~130 teams), includes SEC, Big Ten, etc.
            - FCS: Second division (~120 teams), smaller schools
            - Group 80 = FBS, Group 81 = FCS
            
            College vs NFL:
            - More games per week (50+ vs 16)
            - Wider score differentials (blowouts more common)
            - Rankings matter more (for playoffs)
            - More variety in team quality
            
            Why This Matters for Trading:
            College games are harder to predict because:
            1. Bigger talent gaps between teams
            2. Less historical data per team
            3. More variance game-to-game
            
            But this also means more opportunities for edges!
        """
        params = {'groups': group}
        if week:
            params['week'] = week
        if year:
            params['seasonYear'] = year
        
        url = f"{self.base_url}/football/college-football/scoreboard"
        
        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching NCAAF scoreboard: {e}")
            return {'games': [], 'raw_response': None, 'error': str(e)}
        
        # Same parsing as NFL (structure is identical)
        games = self._parse_nfl_games(data)
        
        return {
            'games': games,
            'raw_response': data
        }
    
    def get_nba_scoreboard(self, date_str: Optional[str] = None) -> Dict:
        """
        Get NBA scoreboard data.
        
        Args:
            date_str: Date in YYYYMMDD format (e.g., "20251016")
                     If None, gets today's games
        
        Returns:
            Dictionary with games list
            
        Example:
            >>> client = ESPNClient()
            >>> scoreboard = client.get_nba_scoreboard()
            >>> 
            >>> for game in scoreboard['games']:
            ...     if game['is_live']:
            ...         print(f"LIVE: {game['name']}")
            ...         print(f"  Q{game['period']}, {game['clock']}")
        
        Educational Notes:
            NBA Schedule:
            - Regular season: October-April (~82 games per team)
            - Playoffs: April-June (best-of-7 series)
            - Multiple games per day (10-15 games on busy nights)
            
            NBA vs NFL Trading:
            - More games = more opportunities
            - Higher scoring = different probability models
            - Individual players matter more (injuries crucial)
            - Home court advantage smaller than NFL
            
            Phase 6+: When we add NBA trading, we'll need:
            1. Player injury tracking
            2. Back-to-back game fatigue models
            3. Playoff vs regular season adjustments
        """
        params = {}
        if date_str:
            params['dates'] = date_str
        
        url = f"{self.base_url}/basketball/nba/scoreboard"
        
        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching NBA scoreboard: {e}")
            return {'games': [], 'raw_response': None, 'error': str(e)}
        
        games = self._parse_nfl_games(data)  # Same structure!
        
        return {
            'games': games,
            'raw_response': data
        }
    
    def monitor_live_games(
        self,
        sport: str = "nfl",
        callback=None,
        poll_interval: int = 15
    ):
        """
        Continuously monitor live games and call callback on updates.
        
        Args:
            sport: "nfl", "ncaaf", or "nba"
            callback: Function to call with game data: callback(games)
            poll_interval: Seconds between checks (default 15)
        
        Example:
            >>> def on_game_update(games):
            ...     for game in games:
            ...         if game['is_live']:
            ...             print(f"Update: {game['name']} - {game['home_score']}-{game['away_score']}")
            >>> 
            >>> client = ESPNClient()
            >>> client.monitor_live_games(sport="nfl", callback=on_game_update)
            # Runs forever, calling callback every 15 seconds
        
        Educational Notes:
            This is a "blocking" function - it runs forever in a loop.
            
            In production (Phase 3+), we'll use:
            - APScheduler for cron-like scheduling
            - Async/await for non-blocking operation
            - WebSockets for real-time updates (if available)
            
            But for Phase 2, this simple polling approach works great!
            
            Polling Tradeoffs:
            - Too fast (every 5s): Wastes bandwidth, might anger ESPN
            - Too slow (every 60s): Miss important updates
            - 15-30s is sweet spot for live sports
            
            Why 15 seconds?
            - Scores don't change every second
            - ESPN updates every 10-15s anyway
            - Respectful to their servers
            - Fast enough for trading decisions
        """
        # Get scoreboard function based on sport
        scoreboard_funcs = {
            'nfl': self.get_nfl_scoreboard,
            'ncaaf': self.get_ncaaf_scoreboard,
            'nba': self.get_nba_scoreboard
        }
        
        get_scoreboard = scoreboard_funcs.get(sport.lower())
        if not get_scoreboard:
            raise ValueError(f"Unknown sport: {sport}. Must be 'nfl', 'ncaaf', or 'nba'")
        
        print(f"🔄 Starting live monitor for {sport.upper()} (poll every {poll_interval}s)")
        print("Press Ctrl+C to stop")
        
        try:
            while True:
                # Fetch current games
                scoreboard = get_scoreboard()
                games = scoreboard['games']
                
                # Filter to just live games
                live_games = [g for g in games if g['is_live']]
                
                if live_games:
                    print(f"\n⚡ {len(live_games)} live games")
                    
                    # Call callback if provided
                    if callback:
                        callback(live_games)
                else:
                    print(f"\n💤 No live games right now")
                
                # Wait before next check
                time.sleep(poll_interval)
                
        except KeyboardInterrupt:
            print("\n\n🛑 Monitor stopped")


# Example usage and testing
if __name__ == "__main__":
    """
    Test script to verify ESPN API is working.
    
    Run this to make sure everything is set up correctly:
        python api_connectors/espn_client.py
    """
    client = ESPNClient()
    
    print("=" * 60)
    print("ESPN API CLIENT - TEST SCRIPT")
    print("=" * 60)
    
    # Test NFL
    print("\n📊 Fetching NFL scoreboard...")
    nfl = client.get_nfl_scoreboard()
    print(f"✅ Found {len(nfl['games'])} NFL games")
    
    if nfl['games']:
        print("\nSample NFL game:")
        game = nfl['games'][0]
        print(f"  {game['away_team']} @ {game['home_team']}")
        print(f"  Score: {game['away_score']}-{game['home_score']}")
        print(f"  Status: {game['status']}")
        if game['is_live']:
            print(f"  🔴 LIVE - Q{game['period']}, {game['clock']}")
    
    # Test NCAAF
    print("\n📊 Fetching NCAAF scoreboard...")
    ncaaf = client.get_ncaaf_scoreboard()
    print(f"✅ Found {len(ncaaf['games'])} college football games")
    
    # Count live games
    live_nfl = sum(1 for g in nfl['games'] if g['is_live'])
    live_ncaaf = sum(1 for g in ncaaf['games'] if g['is_live'])
    
    print(f"\n⚡ Live games: {live_nfl} NFL, {live_ncaaf} NCAAF")
    
    print("\n✅ ESPN API client is working!")
```

### ESPN Data Structure Reference

**Parsed Game Object:**
```python
{
    # Game identifiers
    'id': '401547516',                    # ESPN game ID
    'date': '2025-01-16T18:00Z',         # ISO timestamp
    'name': 'Kansas City Chiefs at Buffalo Bills',
    'short_name': 'KC @ BUF',
    
    # Home team
    'home_team': 'Buffalo Bills',
    'home_abbr': 'BUF',
    'home_score': 24,
    'home_record': '14-4',
    
    # Away team
    'away_team': 'Kansas City Chiefs',
    'away_abbr': 'KC',
    'away_score': 27,
    'away_record': '15-3',
    
    # Game state
    'status': 'STATUS_IN_PROGRESS',       # or STATUS_FINAL, STATUS_SCHEDULED
    'period': 4,                          # Quarter (1-4, 5+ for OT)
    'clock': '2:45',                      # Time remaining in period
    
    # Convenience flags
    'is_live': True,                      # Game currently in progress?
    'is_final': False,                    # Game over?
    
    # Venue
    'venue': 'Highmark Stadium',
    'city': 'Orchard Park',
    
    # Calculated fields (useful for odds)
    'lead': 3,                            # Point differential
    'leader': 'away'                      # 'home', 'away', or 'tied'
}
```

---

## Balldontlie NFL API (Phase 2)

### Overview

Balldontlie provides an alternative NFL data source. Good as a **backup** to ESPN if their API is down.

**Key Features:**
- Official NFL data
- Requires free API key
- Rate limits: 5 requests/minute (free tier)
- Paid tiers available for higher limits

**When to use:**
- ESPN API fails or is slow
- Need official NFL data source
- Want redundancy in data pipeline

**Free Tier Limitations:**
- 5 requests/minute = 300 requests/hour
- Enough for monitoring ~20-30 live games
- Not enough for high-frequency polling

### Getting API Key

1. Visit https://nfl.balldontlie.io/
2. Sign up for free account
3. Get API key from dashboard
4. Add to `.env`:
   ```bash
   BALLDONTLIE_API_KEY=your_api_key_here
   ```

### Balldontlie Client Implementation

```python
# api_connectors/balldontlie_client.py

"""
Balldontlie NFL API Client.

This is a BACKUP data source to ESPN. Use when:
1. ESPN API is down or slow
2. Need official NFL data
3. Want redundancy in data pipeline

Rate Limits (FREE TIER):
- 5 requests per minute
- 300 requests per hour
- Enough for ~20-30 live games

Educational Notes:
------------------
Why have multiple data sources?

1. RELIABILITY: If one API goes down, we keep working
2. ACCURACY: Cross-check data between sources
3. COMPLIANCE: Some use cases require "official" data

This is called "data source redundancy" and is crucial for
production systems. Always have a backup!

Paid Tiers:
- Standard: $10/month, 30 req/min
- Pro: $25/month, 60 req/min  
- Enterprise: Custom pricing

For Phase 2-3, free tier is fine. Upgrade if needed in Phase 5+.
"""

import requests
import os
from typing import Dict, List, Optional
from datetime import datetime, date
from dotenv import load_dotenv
import time

load_dotenv()


class BalldontlieClient:
    """
    Client for Balldontlie NFL API.
    
    Provides backup NFL data source with official statistics.
    Requires API key (free tier available).
    
    Usage:
        client = BalldontlieClient()
        
        # Get games for specific date
        games = client.get_games(date="2025-10-16")
        
        # Get live games
        live_games = client.get_live_games()
    
    Rate Limiting:
        Free tier: 5 requests/minute
        This client automatically handles rate limiting with delays.
    """
    
    def __init__(self):
        """
        Initialize Balldontlie client.
        
        Raises:
            EnvironmentError: If BALLDONTLIE_API_KEY not in environment
            
        Educational Note:
            We load the API key from environment variables for security.
            Never hardcode API keys in your code!
            
            Why?
            1. Keys in code can leak if you share code
            2. Keys in Git history are compromised forever
            3. Different keys for dev/prod environments
            
            Always use .env files for secrets!
        """
        self.base_url = "https://api.balldontlie.io/v1/nfl"
        self.api_key = os.getenv('BALLDONTLIE_API_KEY')
        
        if not self.api_key:
            raise EnvironmentError(
                "BALLDONTLIE_API_KEY not found in environment. "
                "Please add to .env file."
            )
        
        # Session for connection pooling
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.api_key}'
        })
        
        # Rate limiting
        self.requests_per_minute = 5
        self.min_request_interval = 60.0 / self.requests_per_minute  # 12 seconds
        self.last_request_time = 0
    
    def _rate_limit(self):
        """
        Enforce rate limiting by adding delays between requests.
        
        Free tier: 5 requests/minute = 1 request every 12 seconds
        
        Educational Note:
            Rate limiting is crucial to avoid getting banned!
            
            How it works:
            1. Track when we last made a request
            2. Calculate how long to wait (12 seconds for free tier)
            3. Sleep if needed before next request
            
            Example:
            - Request at 10:00:00
            - Next request at 10:00:05 → wait 7 more seconds
            - Next request at 10:00:15 → no wait needed (12s passed)
            
            This is called "token bucket" rate limiting.
        """
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.min_request_interval:
            wait_time = self.min_request_interval - time_since_last
            print(f"⏳ Rate limit: waiting {wait_time:.1f}s...")
            time.sleep(wait_time)
        
        self.last_request_time = time.time()
    
    def get_games(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        season: Optional[int] = None
    ) -> List[Dict]:
        """
        Get NFL games within date range.
        
        Args:
            start_date: Start date in YYYY-MM-DD format (e.g., "2025-10-16")
            end_date: End date in YYYY-MM-DD format
            season: Season year (e.g., 2025)
        
        Returns:
            List of game dictionaries
            
        Example:
            >>> client = BalldontlieClient()
            >>> games = client.get_games(start_date="2025-10-16")
            >>> 
            >>> for game in games:
            ...     print(f"{game['away_team']} @ {game['home_team']}")
            ...     if game['status'] == 'Final':
            ...         print(f"  Final: {game['away_score']}-{game['home_score']}")
        
        Educational Notes:
            Date Ranges:
            - Single day: set start_date = end_date
            - Week: start_date = Monday, end_date = Monday+7
            - Season: set season parameter
            
            Response includes:
            - Scheduled games (future)
            - In-progress games (live)
            - Completed games (final)
            
            Filter by status in your code if needed!
        """
        self._rate_limit()
        
        params = {}
        if start_date:
            params['start_date'] = start_date
        if end_date:
            params['end_date'] = end_date
        if season:
            params['season'] = season
        
        url = f"{self.base_url}/games"
        
        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching Balldontlie games: {e}")
            return []
        
        return data.get('data', [])
    
    def get_live_games(self) -> List[Dict]:
        """
        Get currently live NFL games.
        
        Returns:
            List of in-progress games
            
        Example:
            >>> client = BalldontlieClient()
            >>> live = client.get_live_games()
            >>> 
            >>> if live:
            ...     print(f"🔴 {len(live)} live games!")
            ...     for game in live:
            ...         print(f"  {game['home_team']} vs {game['away_team']}")
            ... else:
            ...     print("No live games right now")
        
        Educational Note:
            This is a convenience method that:
            1. Gets today's games
            2. Filters to status = "In Progress"
            
            Same result as:
                games = client.get_games(start_date=today)
                live = [g for g in games if g['status'] == 'In Progress']
            
            But cleaner API for common use case!
        """
        today = date.today().isoformat()
        games = self.get_games(start_date=today, end_date=today)
        
        # Filter to in-progress games
        live_games = [
            g for g in games 
            if g.get('status') == 'In Progress'
        ]
        
        return live_games


# Comparison: ESPN vs Balldontlie
if __name__ == "__main__":
    """
    Side-by-side comparison of ESPN and Balldontlie APIs.
    
    This helps you understand the tradeoffs:
    - ESPN: Faster, no key, more flexible
    - Balldontlie: Official data, rate limited
    """
    from .espn_client import ESPNClient
    
    print("=" * 60)
    print("API COMPARISON: ESPN vs BALLDONTLIE")
    print("=" * 60)
    
    # ESPN
    print("\n📊 ESPN API:")
    espn = ESPNClient()
    start = time.time()
    espn_games = espn.get_nfl_scoreboard()
    espn_time = time.time() - start
    print(f"  ✅ {len(espn_games['games'])} games in {espn_time:.2f}s")
    print(f"  ⚡ No rate limits!")
    print(f"  🆓 No API key required")
    
    # Balldontlie
    print("\n📊 Balldontlie API:")
    try:
        bdl = BalldontlieClient()
        start = time.time()
        today = date.today().isoformat()
        bdl_games = bdl.get_games(start_date=today)
        bdl_time = time.time() - start
        print(f"  ✅ {len(bdl_games)} games in {bdl_time:.2f}s")
        print(f"  ⏳ Rate limit: 5 req/min (free tier)")
        print(f"  🔑 API key required")
    except EnvironmentError as e:
        print(f"  ❌ {e}")
    
    print("\n📋 RECOMMENDATION:")
    print("  PRIMARY: Use ESPN (faster, no limits)")
    print("  BACKUP: Use Balldontlie (if ESPN fails)")
    print("  PHASE 2: Implement fallback logic")
```

---

## Weather API Integration (Phase 2)

### Overview

Weather impacts game outcomes, especially in outdoor sports. Wind, rain, snow, and cold temperatures all affect scoring.

**Why Weather Matters for Trading:**
- **Wind**: Reduces passing efficiency, lowers scores
- **Rain/Snow**: More fumbles, fewer points, run-heavy
- **Cold**: Affects ball handling, kicking accuracy
- **Dome games**: No weather impact (control group!)

**Research shows:**
- Games with 15+ MPH wind: 3-5 fewer points scored
- Rain/snow games: 20-30% fewer passing yards
- Cold games (<32°F): Field goals 5-10% less accurate

**When to use weather data:**
- Phase 2: Basic integration, log weather conditions
- Phase 4: Incorporate into odds models
- Phase 7: Advanced weather adjustments (wind speed, precipitation rate)

### Recommended API: OpenWeatherMap

After extensive research, **OpenWeatherMap** is the best choice:

✅ **Pros:**
- Free tier: 1000 calls/day (enough for Phase 2-4)
- Historical data available
- 5-day forecast for upcoming games
- Excellent documentation
- Global coverage (for international expansion)
- Hourly updates

✅ **Pricing:**
- Free: 1000 calls/day, current + 5-day forecast
- Startup ($40/mo): 100k calls/day, historical data
- Developer ($120/mo): 1M calls/day, minute-by-minute

**Alternative considered:**
- WeatherAPI.com: Good, but less historical data
- Tomorrow.io: Great but expensive ($500+/mo)
- NOAA: Free but US-only, harder to use

### Getting OpenWeatherMap API Key

1. Visit https://openweathermap.org/api
2. Sign up for free account
3. Get API key (appears in your dashboard)
4. Add to `.env`:
   ```bash
   OPENWEATHER_API_KEY=your_api_key_here
   ```

### Stadium Coordinates Database

NFL and NCAAF stadiums with GPS coordinates for weather lookups:

```python
# data/stadium_coordinates.py

"""
NFL and NCAAF Stadium Coordinates.

This database maps stadiums to GPS coordinates for weather API lookups.

Educational Notes:
------------------
Why we need this:
- Weather APIs require lat/lon coordinates
- Stadium addresses aren't precise enough
- GPS coords ensure we get weather AT the stadium, not nearby

How to use:
1. Look up stadium name from ESPN game data
2. Get (lat, lon) from this database
3. Query weather API with those coordinates

Data source: Public stadium information, verified via Google Maps
"""

NFL_STADIUMS = {
    # AFC East
    "Gillette Stadium": {"lat": 42.0909, "lon": -71.2643, "dome": False},
    "Highmark Stadium": {"lat": 42.7738, "lon": -78.7870, "dome": False},
    "Hard Rock Stadium": {"lat": 25.9580, "lon": -80.2389, "dome": False},
    "MetLife Stadium": {"lat": 40.8128, "lon": -74.0742, "dome": False},
    
    # AFC North
    "M&T Bank Stadium": {"lat": 39.2780, "lon": -76.6227, "dome": False},
    "Paycor Stadium": {"lat": 39.0954, "lon": -84.5160, "dome": False},
    "FirstEnergy Stadium": {"lat": 41.5061, "lon": -81.6995, "dome": False},
    "Acrisure Stadium": {"lat": 40.4468, "lon": -80.0158, "dome": False},
    
    # AFC South
    "NRG Stadium": {"lat": 29.6847, "lon": -95.4107, "dome": True},  # Retractable
    "Lucas Oil Stadium": {"lat": 39.7601, "lon": -86.1639, "dome": True},  # Retractable
    "TIAA Bank Field": {"lat": 30.3239, "lon": -81.6373, "dome": False},
    "Nissan Stadium": {"lat": 36.1665, "lon": -86.7713, "dome": False},
    
    # AFC West
    "Empower Field at Mile High": {"lat": 39.7439, "lon": -105.0201, "dome": False},
    "Arrowhead Stadium": {"lat": 39.0489, "lon": -94.4839, "dome": False},
    "Allegiant Stadium": {"lat": 36.0909, "lon": -115.1833, "dome": True},
    "SoFi Stadium": {"lat": 33.9535, "lon": -118.3390, "dome": True},
    
    # NFC East
    "AT&T Stadium": {"lat": 32.7473, "lon": -97.0945, "dome": True},  # Retractable
    "MetLife Stadium": {"lat": 40.8128, "lon": -74.0742, "dome": False},  # Giants/Jets
    "Lincoln Financial Field": {"lat": 39.9008, "lon": -75.1675, "dome": False},
    "FedExField": {"lat": 38.9076, "lon": -76.8645, "dome": False},
    
    # NFC North
    "Soldier Field": {"lat": 41.8623, "lon": -87.6167, "dome": False},
    "Ford Field": {"lat": 42.3400, "lon": -83.0456, "dome": True},
    "Lambeau Field": {"lat": 44.5013, "lon": -88.0622, "dome": False},  # Outdoor in GB!
    "U.S. Bank Stadium": {"lat": 44.9736, "lon": -93.2577, "dome": True},
    
    # NFC South
    "Mercedes-Benz Stadium": {"lat": 33.7553, "lon": -84.4006, "dome": True},  # Retractable
    "Bank of America Stadium": {"lat": 35.2258, "lon": -80.8528, "dome": False},
    "Caesars Superdome": {"lat": 29.9511, "lon": -90.0812, "dome": True},
    "Raymond James Stadium": {"lat": 27.9759, "lon": -82.5033, "dome": False},
    
    # NFC West
    "State Farm Stadium": {"lat": 33.5276, "lon": -112.2626, "dome": True},  # Retractable
    "Levi's Stadium": {"lat": 37.4032, "lon": -121.9698, "dome": False},
    "Lumen Field": {"lat": 47.5952, "lon": -122.3316, "dome": False},  # Partial roof
    "SoFi Stadium": {"lat": 33.9535, "lon": -118.3390, "dome": True},  # Rams/Chargers
}

# Top 25 NCAAF stadiums (expand as needed)
NCAAF_STADIUMS = {
    "Michigan Stadium": {"lat": 42.2658, "lon": -83.7488, "dome": False},
    "Beaver Stadium": {"lat": 40.8122, "lon": -77.8563, "dome": False},
    "Ohio Stadium": {"lat": 40.0018, "lon": -83.0197, "dome": False},
    "Kyle Field": {"lat": 30.6099, "lon": -96.3402, "dome": False},
    "Neyland Stadium": {"lat": 35.9550, "lon": -83.9250, "dome": False},
    "Tiger Stadium": {"lat": 30.4121, "lon": -91.1839, "dome": False},  # LSU
    "Bryant-Denny Stadium": {"lat": 33.2080, "lon": -87.5502, "dome": False},
    "Darrell K Royal-Texas Memorial Stadium": {"lat": 30.2839, "lon": -97.7323, "dome": False},
    "Sanford Stadium": {"lat": 33.9497, "lon": -83.3733, "dome": False},  # Georgia
    "Ben Hill Griffin Stadium": {"lat": 29.6500, "lon": -82.3486, "dome": False},  # Florida
    # Add more as needed for markets you trade
}

def get_stadium_coords(stadium_name: str) -> Optional[Dict]:
    """
    Get coordinates for a stadium.
    
    Args:
        stadium_name: Name of stadium (from ESPN data)
        
    Returns:
        Dict with lat, lon, dome status, or None if not found
        
    Example:
        >>> coords = get_stadium_coords("Lambeau Field")
        >>> print(coords)
        {'lat': 44.5013, 'lon': -88.0622, 'dome': False}
    """
    # Check NFL first
    if stadium_name in NFL_STADIUMS:
        return NFL_STADIUMS[stadium_name]
    
    # Check NCAAF
    if stadium_name in NCAAF_STADIUMS:
        return NCAAF_STADIUMS[stadium_name]
    
    return None
```

### OpenWeatherMap Client Implementation

```python
# api_connectors/weather_client.py

"""
OpenWeatherMap API Client for Game Weather Data.

Fetches weather conditions at stadium locations to incorporate into
odds models and trading decisions.

Educational Notes:
------------------
Why weather matters in sports betting:

1. WIND: Major impact on passing games
   - <10 MPH: No significant effect
   - 10-15 MPH: Slight reduction in passing
   - 15-20 MPH: Moderate impact, favor run game
   - 20+ MPH: Major impact, significant scoring reduction

2. PRECIPITATION:
   - Rain: More fumbles, fewer passes, lower scores
   - Snow: Even more pronounced effect
   - Heavy precipitation: Games become unpredictable

3. TEMPERATURE:
   - Cold (<32°F): Affects ball handling, kicking
   - Extreme cold (<20°F): Major impact on all aspects
   - Heat (>90°F): Fatigue factor, especially late game

4. DOME GAMES:
   - No weather impact (perfect conditions)
   - These become our "control group" for models

Research-backed adjustments (Phase 4+):
- 15 MPH wind: -3 to -5 points total score
- Rain: -4 to -7 points total score
- Snow: -6 to -10 points total score
- Cold (<20°F): -2 to -4 points, FG% down 5-10%
"""

import requests
import os
from typing import Dict, Optional
from datetime import datetime
from dotenv import load_dotenv
from .stadium_coordinates import get_stadium_coords

load_dotenv()


class WeatherClient:
    """
    Client for OpenWeatherMap API.
    
    Fetches current and forecast weather data for stadium locations.
    
    Usage:
        weather = WeatherClient()
        
        # Get current weather at stadium
        conditions = weather.get_current_weather("Lambeau Field")
        print(f"Temp: {conditions['temp_f']}°F, Wind: {conditions['wind_mph']} MPH")
        
        # Assess game impact
        impact = weather.assess_game_impact(conditions)
        if impact['severity'] == 'major':
            print(f"⚠️ Weather alert: {impact['description']}")
    """
    
    def __init__(self):
        """
        Initialize weather client.
        
        Raises:
            EnvironmentError: If OPENWEATHER_API_KEY not in environment
        """
        self.base_url = "https://api.openweathermap.org/data/2.5"
        self.api_key = os.getenv('OPENWEATHER_API_KEY')
        
        if not self.api_key:
            raise EnvironmentError(
                "OPENWEATHER_API_KEY not found in environment. "
                "Sign up at https://openweathermap.org/api and add to .env"
            )
        
        self.session = requests.Session()
    
    def get_current_weather(self, stadium_name: str) -> Optional[Dict]:
        """
        Get current weather at a stadium.
        
        Args:
            stadium_name: Name of stadium (e.g., "Lambeau Field")
            
        Returns:
            Weather dictionary with:
            - temp_f: Temperature in Fahrenheit
            - feels_like_f: Feels-like temperature
            - humidity: Humidity percentage
            - wind_mph: Wind speed in MPH
            - wind_direction: Wind direction (N, NE, E, etc.)
            - conditions: Description (e.g., "Clear", "Rain", "Snow")
            - precipitation: Precipitation type (none, rain, snow)
            - dome: Is this a dome stadium? (always perfect if True)
            
        Returns None if stadium not found or API error.
        
        Example:
            >>> weather = WeatherClient()
            >>> conditions = weather.get_current_weather("Lambeau Field")
            >>> 
            >>> if conditions:
            ...     print(f"Lambeau Field weather:")
            ...     print(f"  Temp: {conditions['temp_f']}°F")
            ...     print(f"  Wind: {conditions['wind_mph']} MPH")
            ...     print(f"  Conditions: {conditions['conditions']}")
            ...     
            ...     if conditions['dome']:
            ...         print("  (Dome stadium - weather doesn't matter!)")
        
        Educational Notes:
            API Response: OpenWeatherMap returns temp in Kelvin by default!
            We convert to Fahrenheit: F = (K - 273.15) * 9/5 + 32
            
            Why Fahrenheit? US sports use Fahrenheit, so easier to think about.
            "20°F is really cold" vs "266K is really cold" 😄
            
            Wind direction: Degrees converted to compass points:
            - 0°/360° = N (North)
            - 90° = E (East)
            - 180° = S (South)
            - 270° = W (West)
        """
        # Get stadium coordinates
        coords = get_stadium_coords(stadium_name)
        if not coords:
            print(f"⚠️  Stadium not found: {stadium_name}")
            return None
        
        # If dome stadium, return perfect conditions (weather doesn't matter!)
        if coords['dome']:
            return {
                'temp_f': 72.0,
                'feels_like_f': 72.0,
                'humidity': 40,
                'wind_mph': 0.0,
                'wind_direction': 'N',
                'conditions': 'Perfect (Dome)',
                'precipitation': 'none',
                'dome': True,
                'raw_data': None
            }
        
        # Fetch weather from API
        params = {
            'lat': coords['lat'],
            'lon': coords['lon'],
            'appid': self.api_key,
            'units': 'metric'  # We'll convert to imperial ourselves
        }
        
        try:
            response = self.session.get(
                f"{self.base_url}/weather",
                params=params,
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching weather: {e}")
            return None
        
        # Parse and convert
        temp_c = data['main']['temp']
        feels_like_c = data['main']['feels_like']
        
        # Convert Celsius to Fahrenheit
        temp_f = temp_c * 9/5 + 32
        feels_like_f = feels_like_c * 9/5 + 32
        
        # Wind speed: m/s to MPH
        wind_ms = data['wind']['speed']
        wind_mph = wind_ms * 2.237
        
        # Wind direction: degrees to compass
        wind_deg = data['wind'].get('deg', 0)
        wind_direction = self._degrees_to_compass(wind_deg)
        
        # Precipitation type
        precipitation = 'none'
        if 'rain' in data:
            precipitation = 'rain'
        elif 'snow' in data:
            precipitation = 'snow'
        
        weather_data = {
            'temp_f': round(temp_f, 1),
            'feels_like_f': round(feels_like_f, 1),
            'humidity': data['main']['humidity'],
            'wind_mph': round(wind_mph, 1),
            'wind_direction': wind_direction,
            'conditions': data['weather'][0]['main'],
            'description': data['weather'][0]['description'],
            'precipitation': precipitation,
            'dome': False,
            'raw_data': data  # Keep full response for debugging
        }
        
        return weather_data
    
    def _degrees_to_compass(self, degrees: float) -> str:
        """
        Convert wind direction from degrees to compass point.
        
        Args:
            degrees: 0-360 degrees (0 = North, 90 = East, etc.)
            
        Returns:
            Compass direction (N, NE, E, SE, S, SW, W, NW)
            
        Educational Note:
            We divide the circle into 8 sectors (45° each):
            - 337.5° to 22.5° = N
            - 22.5° to 67.5° = NE
            - 67.5° to 112.5° = E
            And so on...
            
            This is simpler than raw degrees for humans to understand.
        """
        directions = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
        index = round(degrees / 45) % 8
        return directions[index]
    
    def assess_game_impact(self, weather: Dict) -> Dict:
        """
        Assess how weather will impact game.
        
        Args:
            weather: Weather data from get_current_weather()
            
        Returns:
            Impact assessment with:
            - severity: 'none', 'minor', 'moderate', 'major'
            - description: Human-readable description
            - scoring_adjustment: Estimated points impact (negative = lower scoring)
            - confidence: 'high', 'medium', 'low'
            
        Example:
            >>> weather = client.get_current_weather("Lambeau Field")
            >>> impact = client.assess_game_impact(weather)
            >>> 
            >>> print(f"Impact: {impact['severity']}")
            >>> print(f"Description: {impact['description']}")
            >>> print(f"Scoring adjustment: {impact['scoring_adjustment']} points")
            >>> 
            >>> if impact['severity'] in ['major', 'moderate']:
            ...     print("⚠️  Weather is a factor - adjust odds accordingly!")
        
        Educational Notes:
            This implements research-backed weather adjustments:
            
            WIND IMPACT:
            - <10 MPH: Negligible
            - 10-15 MPH: Minor (-1 to -2 points)
            - 15-20 MPH: Moderate (-3 to -5 points)
            - 20+ MPH: Major (-5 to -8 points)
            
            PRECIPITATION:
            - Light rain: -2 to -4 points
            - Heavy rain: -4 to -7 points
            - Snow: -6 to -10 points
            
            TEMPERATURE:
            - Cold (20-32°F): -2 to -4 points
            - Extreme cold (<20°F): -4 to -6 points
            
            These are GUIDELINES, not absolutes! Actual impact depends on:
            - Team playing styles (run vs pass heavy)
            - Player experience in conditions
            - Home field advantage (home team used to it)
            
            Phase 4+: Build statistical models using historical data.
            For now, use these as starting points.
        """
        # Dome stadiums = no weather impact
        if weather['dome']:
            return {
                'severity': 'none',
                'description': 'Dome stadium - perfect conditions',
                'scoring_adjustment': 0.0,
                'confidence': 'high'
            }
        
        severity = 'none'
        factors = []
        scoring_adj = 0.0
        
        # Check wind
        wind = weather['wind_mph']
        if wind >= 20:
            severity = 'major'
            factors.append(f'high wind ({wind} MPH)')
            scoring_adj -= 6.0
        elif wind >= 15:
            severity = 'moderate' if severity == 'none' else severity
            factors.append(f'moderate wind ({wind} MPH)')
            scoring_adj -= 4.0
        elif wind >= 10:
            severity = 'minor' if severity == 'none' else severity
            factors.append(f'breezy ({wind} MPH)')
            scoring_adj -= 2.0
        
        # Check precipitation
        precip = weather['precipitation']
        if precip == 'snow':
            severity = 'major'
            factors.append('snow')
            scoring_adj -= 8.0
        elif precip == 'rain':
            if severity != 'major':
                severity = 'moderate'
            factors.append('rain')
            scoring_adj -= 5.0
        
        # Check temperature
        temp = weather['temp_f']
        if temp < 20:
            severity = 'major' if severity == 'none' else severity
            factors.append(f'extreme cold ({temp}°F)')
            scoring_adj -= 5.0
        elif temp < 32:
            severity = 'minor' if severity == 'none' else severity
            factors.append(f'freezing ({temp}°F)')
            scoring_adj -= 3.0
        
        # Build description
        if not factors:
            description = f"Good conditions - {temp}°F, {wind} MPH wind"
        else:
            description = f"Challenging: {', '.join(factors)}"
        
        return {
            'severity': severity,
            'description': description,
            'scoring_adjustment': round(scoring_adj, 1),
            'confidence': 'high' if len(factors) >= 2 else 'medium'
        }


# Example usage
if __name__ == "__main__":
    """
    Test weather API and see example output.
    """
    client = WeatherClient()
    
    print("=" * 60)
    print("WEATHER API CLIENT - TEST SCRIPT")
    print("=" * 60)
    
    # Test a few notable stadiums
    test_stadiums = [
        "Lambeau Field",         # Outdoor, cold weather
        "AT&T Stadium",          # Dome (retractable)
        "Soldier Field",         # Outdoor, Chicago weather
        "Empower Field at Mile High"  # High altitude, outdoor
    ]
    
    for stadium in test_stadiums:
        print(f"\n📍 {stadium}")
        print("-" * 60)
        
        weather = client.get_current_weather(stadium)
        
        if weather:
            print(f"  🌡️  Temp: {weather['temp_f']}°F (feels like {weather['feels_like_f']}°F)")
            print(f"  💨 Wind: {weather['wind_mph']} MPH {weather['wind_direction']}")
            print(f"  ☁️  Conditions: {weather['conditions']}")
            if weather['precipitation'] != 'none':
                print(f"  🌧️  Precipitation: {weather['precipitation']}")
            
            # Assess impact
            impact = client.assess_game_impact(weather)
            print(f"\n  📊 Game Impact: {impact['severity'].upper()}")
            print(f"     {impact['description']}")
            if impact['scoring_adjustment'] != 0:
                print(f"     Expected scoring: {impact['scoring_adjustment']:+.1f} points")
        else:
            print("  ❌ Could not fetch weather")
    
    print("\n" + "=" * 60)
    print("✅ Weather API client is working!")
```

---

## Rate Limiting Strategy

### Why Rate Limiting Matters

**Educational Overview:**

Rate limiting is crucial for several reasons:

1. **Avoid Getting Banned**: APIs track your usage and will block you if you abuse them
2. **Be Respectful**: Other developers share the same API infrastructure
3. **Cost Control**: Paid tiers charge per request
4. **System Stability**: Prevents overwhelming your own system

**Common Mistakes:**
- ❌ Making hundreds of requests in a loop without delays
- ❌ Not tracking request counts
- ❌ Ignoring 429 (Too Many Requests) errors
- ❌ No fallback when rate limited

**Best Practices:**
- ✅ Track requests per minute/hour/day
- ✅ Add delays between requests
- ✅ Implement exponential backoff on errors
- ✅ Cache responses when possible
- ✅ Use batch operations when available

### Rate Limit Summary by API

| API | Free Tier Limit | Recommended Strategy |
|-----|-----------------|---------------------|
| Kalshi | No published limit | Respect 429 errors, use WebSocket for real-time |
| ESPN | ~500 req/hour (estimated) | 1 request per 7-10 seconds, cache results |
| Balldontlie | 5 req/min | 1 request per 12 seconds minimum |
| OpenWeather | 1000 req/day | Cache weather for 15-30 minutes |

### Implementation: Rate Limiter Class

```python
# utils/rate_limiter.py

"""
Rate Limiting Utilities for API Clients.

Prevents exceeding API rate limits through:
1. Token bucket algorithm (smooth rate limiting)
2. Request tracking and logging
3. Automatic delays between requests
4. Exponential backoff on errors

Educational Notes:
------------------
Token Bucket Algorithm:

Imagine a bucket that:
1. Starts with N tokens (your rate limit)
2. Loses 1 token per request
3. Refills tokens over time (e.g., 5 tokens per minute)
4. When empty, you must wait for refill

This allows "bursts" of requests while maintaining average rate.

Example:
- Limit: 5 requests/minute
- Bucket starts with 5 tokens
- Make 5 requests instantly (bucket now empty)
- Wait 60 seconds for refill
- Make 5 more requests

This is better than "1 request every 12 seconds" because:
- More flexible (can burst when needed)
- More efficient (no wasted time if requests are spaced out)
- Industry standard algorithm
"""

import time
from collections import deque
from typing import Optional
import threading


class RateLimiter:
    """
    Token bucket rate limiter.
    
    Ensures API requests don't exceed specified rate limits.
    Thread-safe for concurrent usage.
    
    Usage:
        # 5 requests per minute
        limiter = RateLimiter(requests_per_period=5, period_seconds=60)
        
        for i in range(100):
            limiter.wait()  # Blocks if rate limit would be exceeded
            make_api_request()
    """
    
    def __init__(
        self,
        requests_per_period: int,
        period_seconds: float = 60.0,
        burst_size: Optional[int] = None
    ):
        """
        Initialize rate limiter.
        
        Args:
            requests_per_period: Max requests allowed in period
            period_seconds: Time period in seconds (default 60)
            burst_size: Max burst size (default = requests_per_period)
            
        Example:
            # Balldontlie: 5 requests per minute
            limiter = RateLimiter(requests_per_period=5, period_seconds=60)
            
            # ESPN: 500 requests per hour (roughly 8-9 per minute)
            limiter = RateLimiter(requests_per_period=8, period_seconds=60)
        
        Educational Note:
            burst_size lets you make multiple requests quickly,
            as long as you don't exceed the average rate.
            
            Example: 5 req/min with burst_size=5
            - Can make 5 requests instantly
            - Then must wait 60 seconds for refill
            
            vs burst_size=1:
            - Must wait 12 seconds between each request
            - No bursting allowed
        """
        self.requests_per_period = requests_per_period
        self.period_seconds = period_seconds
        self.burst_size = burst_size or requests_per_period
        
        # Track recent request timestamps
        self.request_times = deque(maxlen=self.burst_size)
        
        # Thread safety
        self.lock = threading.Lock()
        
        # Calculate minimum delay between requests
        self.min_delay = period_seconds / requests_per_period
    
    def wait(self):
        """
        Wait if necessary to respect rate limit.
        
        This method blocks (sleeps) if making a request now would
        exceed the rate limit.
        
        Educational Note:
            This is a "blocking" operation - your code stops here
            until it's safe to proceed.
            
            In async code (Phase 3+), use asyncio.sleep() instead.
            For now, time.sleep() is simpler and works fine.
        """
        with self.lock:
            current_time = time.time()
            
            # If we're at burst limit, check oldest request
            if len(self.request_times) >= self.burst_size:
                oldest_request = self.request_times[0]
                time_passed = current_time - oldest_request
                
                # If not enough time has passed, wait
                if time_passed < self.period_seconds:
                    wait_time = self.period_seconds - time_passed
                    print(f"⏳ Rate limit: waiting {wait_time:.1f}s...")
                    time.sleep(wait_time)
                    current_time = time.time()
            
            # Record this request
            self.request_times.append(current_time)
    
    def get_wait_time(self) -> float:
        """
        Get time to wait before next request (without blocking).
        
        Returns:
            Seconds to wait (0 if can proceed immediately)
            
        Example:
            >>> limiter = RateLimiter(5, 60)
            >>> wait = limiter.get_wait_time()
            >>> if wait > 0:
            ...     print(f"Rate limited for {wait:.1f} more seconds")
        """
        with self.lock:
            if len(self.request_times) < self.burst_size:
                return 0.0
            
            current_time = time.time()
            oldest_request = self.request_times[0]
            time_passed = current_time - oldest_request
            
            if time_passed < self.period_seconds:
                return self.period_seconds - time_passed
            
            return 0.0
    
    def reset(self):
        """Reset the rate limiter (clear all tracked requests)."""
        with self.lock:
            self.request_times.clear()


class ExponentialBackoff:
    """
    Exponential backoff for retry logic.
    
    When API requests fail, retry with increasing delays:
    - 1st retry: wait 1 second
    - 2nd retry: wait 2 seconds
    - 3rd retry: wait 4 seconds
    - 4th retry: wait 8 seconds
    - etc.
    
    This gives the API time to recover and prevents hammering it.
    
    Usage:
        backoff = ExponentialBackoff(max_retries=5)
        
        for attempt in range(backoff.max_retries):
            try:
                result = make_api_request()
                break  # Success!
            except APIError:
                if attempt < backoff.max_retries - 1:
                    wait_time = backoff.get_wait_time(attempt)
                    print(f"Retry {attempt + 1}/{backoff.max_retries} in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    raise  # Final attempt failed
    
    Educational Notes:
        Why exponential?
        
        Linear backoff (1s, 2s, 3s, 4s...):
        - Still hits API too frequently
        - Doesn't give enough recovery time
        
        Exponential (1s, 2s, 4s, 8s, 16s...):
        - Quickly backs off
        - Gives API time to recover
        - Prevents cascading failures
        
        This is the industry standard for retry logic.
        Used by AWS, Google Cloud, etc.
    """
    
    def __init__(
        self,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        max_retries: int = 5
    ):
        """
        Initialize exponential backoff.
        
        Args:
            base_delay: Initial delay in seconds
            max_delay: Maximum delay in seconds
            max_retries: Maximum number of retries
        """
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.max_retries = max_retries
    
    def get_wait_time(self, attempt: int) -> float:
        """
        Calculate wait time for given attempt number.
        
        Args:
            attempt: Attempt number (0-indexed)
            
        Returns:
            Seconds to wait
            
        Example:
            >>> backoff = ExponentialBackoff()
            >>> for i in range(5):
            ...     print(f"Attempt {i}: wait {backoff.get_wait_time(i)}s")
            Attempt 0: wait 1.0s
            Attempt 1: wait 2.0s
            Attempt 2: wait 4.0s
            Attempt 3: wait 8.0s
            Attempt 4: wait 16.0s
        """
        # Calculate: base_delay * 2^attempt
        wait = self.base_delay * (2 ** attempt)
        
        # Cap at max_delay
        return min(wait, self.max_delay)


# Example integration with API client
if __name__ == "__main__":
    """
    Demonstrate rate limiting in action.
    """
    print("=" * 60)
    print("RATE LIMITER DEMONSTRATION")
    print("=" * 60)
    
    # Create rate limiter: 5 requests per minute
    limiter = RateLimiter(requests_per_period=5, period_seconds=60)
    
    print("\nSimulating 10 API requests (limit: 5 per minute)")
    print("Watch how the rate limiter adds delays...")
    print()
    
    for i in range(10):
        start = time.time()
        
        limiter.wait()  # This will block if necessary
        
        # Simulate API request
        print(f"Request {i + 1}/10 sent at {time.strftime('%H:%M:%S')}")
        
        if i == 4:
            print("\n⏸️  Hit rate limit (5 requests). Must wait before continuing...\n")
    
    print("\n" + "=" * 60)
    print("✅ All requests completed within rate limits!")
```

---

## Error Handling Patterns

### Common API Errors and Solutions

**Educational Overview:**

APIs can fail in many ways. Good error handling is what separates production-ready code from toys.

**Categories of Errors:**

1. **Network Errors**
   - Timeouts
   - Connection refused
   - DNS failures
   
2. **Client Errors (4xx)**
   - 400 Bad Request: Your request is malformed
   - 401 Unauthorized: Bad credentials
   - 403 Forbidden: Valid credentials, but no permission
   - 404 Not Found: Resource doesn't exist
   - 429 Too Many Requests: Rate limited!
   
3. **Server Errors (5xx)**
   - 500 Internal Server Error: Bug on their end
   - 502 Bad Gateway: Server overloaded
   - 503 Service Unavailable: Temporary outage
   - 504 Gateway Timeout: Server too slow

4. **Data Errors**
   - Malformed JSON
   - Missing expected fields
   - Invalid data types

### Error Handling Implementation

```python
# utils/api_error_handler.py

"""
Robust Error Handling for API Clients.

Implements:
1. Automatic retries with exponential backoff
2. Detailed error logging
3. Fallback strategies
4. Circuit breaker pattern (prevent cascading failures)

Educational Notes:
------------------
Why comprehensive error handling?

1. RELIABILITY: Systems fail. Handle it gracefully.
2. DEBUGGING: Good errors save hours of troubleshooting.
3. USER EXPERIENCE: Never show users raw exceptions.
4. DATA INTEGRITY: Don't corrupt database with bad data.

Error Handling Philosophy:
- Fail fast for programmer errors (bugs in our code)
- Retry transient errors (network hiccups)
- Fallback for service outages (use cached data)
- Alert for critical failures (human intervention needed)
"""

import requests
import time
import logging
from typing import Callable, Any, Optional
from functools import wraps
from .rate_limiter import ExponentialBackoff

logger = logging.getLogger(__name__)


class APIError(Exception):
    """Base exception for API errors."""
    pass


class RateLimitError(APIError):
    """Rate limit exceeded."""
    pass


class AuthenticationError(APIError):
    """Authentication failed."""
    pass


class DataError(APIError):
    """Invalid or malformed data."""
    pass


def with_retry(
    max_retries: int = 3,
    backoff: Optional[ExponentialBackoff] = None,
    retry_on: tuple = (requests.exceptions.RequestException,),
    fallback_value: Any = None
):
    """
    Decorator to add retry logic to functions.
    
    Args:
        max_retries: Maximum number of retry attempts
        backoff: ExponentialBackoff instance (default: 1s, 2s, 4s...)
        retry_on: Tuple of exceptions to retry on
        fallback_value: Value to return if all retries fail (else raise)
        
    Example:
        @with_retry(max_retries=3)
        def fetch_data():
            response = requests.get("https://api.example.com/data")
            response.raise_for_status()
            return response.json()
        
        # Will automatically retry up to 3 times on network errors
        data = fetch_data()
    
    Educational Notes:
        Decorators are functions that modify other functions.
        
        @with_retry
        def my_function():
            ...
        
        Is equivalent to:
        
        def my_function():
            ...
        my_function = with_retry(my_function)
        
        Decorators let us add functionality (retries, logging, etc.)
        without cluttering our business logic.
    """
    if backoff is None:
        backoff = ExponentialBackoff(max_retries=max_retries)
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)  # Preserves function metadata
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                
                except retry_on as e:
                    last_exception = e
                    
                    if attempt < max_retries - 1:
                        wait_time = backoff.get_wait_time(attempt)
                        logger.warning(
                            f"{func.__name__} failed (attempt {attempt + 1}/{max_retries}). "
                            f"Retrying in {wait_time}s... Error: {e}"
                        )
                        time.sleep(wait_time)
                    else:
                        logger.error(
                            f"{func.__name__} failed after {max_retries} attempts. "
                            f"Final error: {e}"
                        )
            
            # All retries exhausted
            if fallback_value is not None:
                logger.info(f"Returning fallback value for {func.__name__}")
                return fallback_value
            else:
                raise last_exception
        
        return wrapper
    return decorator


def handle_api_response(response: requests.Response) -> dict:
    """
    Handle API response with comprehensive error checking.
    
    Args:
        response: requests.Response object
        
    Returns:
        Parsed JSON data
        
    Raises:
        RateLimitError: If rate limit exceeded (429)
        AuthenticationError: If auth failed (401, 403)
        APIError: For other HTTP errors
        DataError: If JSON parsing fails
        
    Example:
        response = requests.get(url, headers=headers)
        data = handle_api_response(response)
    
    Educational Notes:
        This centralizes all error handling logic.
        Every API client can use this function rather than
        duplicating error handling code everywhere.
        
        DRY principle: Don't Repeat Yourself!
    """
    # Check for rate limiting
    if response.status_code == 429:
        retry_after = response.headers.get('Retry-After')
        message = f"Rate limit exceeded"
        if retry_after:
            message += f". Retry after {retry_after} seconds"
        
        logger.warning(message)
        raise RateLimitError(message)
    
    # Check for authentication errors
    if response.status_code in [401, 403]:
        logger.error(f"Authentication failed: {response.status_code} {response.text}")
        raise AuthenticationError(f"Auth failed: {response.status_code}")
    
    # Check for other HTTP errors
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error: {e}")
        raise APIError(f"API request failed: {e}")
    
    # Parse JSON
    try:
        data = response.json()
    except ValueError as e:
        logger.error(f"Invalid JSON response: {response.text[:200]}")
        raise DataError(f"Invalid JSON: {e}")
    
    return data


class CircuitBreaker:
    """
    Circuit breaker pattern to prevent cascading failures.
    
    States:
    1. CLOSED: Normal operation, all requests go through
    2. OPEN: Too many failures, all requests fail fast
    3. HALF_OPEN: Testing if service recovered
    
    Example:
        breaker = CircuitBreaker(failure_threshold=5, timeout=60)
        
        def fetch_data():
            with breaker:
                return requests.get(url).json()
        
        # After 5 failures, breaker opens
        # All requests fail fast for 60 seconds
        # Then tries again (half-open state)
    
    Educational Notes:
        Why circuit breakers?
        
        Without circuit breaker:
        - Service goes down
        - We keep trying
        - Every request times out (30+ seconds)
        - Our system becomes unresponsive
        - Users get frustrated
        
        With circuit breaker:
        - Service goes down
        - We detect it quickly (5 failures)
        - Stop sending requests (fail fast in 0.001s)
        - Try again after timeout
        - System stays responsive
        
        This prevents:
        1. Wasting resources on doomed requests
        2. Cascading failures across systems
        3. Making outages worse with traffic
        
        Industry standard for microservices!
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        timeout: float = 60.0,
        name: str = "API"
    ):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Failures before opening circuit
            timeout: Seconds before attempting recovery
            name: Name for logging
        """
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.name = name
        
        self.failures = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    def __enter__(self):
        """Context manager entry."""
        if self.state == "OPEN":
            # Check if timeout has passed
            if time.time() - self.last_failure_time > self.timeout:
                logger.info(f"Circuit breaker {self.name}: Attempting recovery (HALF_OPEN)")
                self.state = "HALF_OPEN"
            else:
                raise APIError(f"Circuit breaker {self.name} is OPEN. Service unavailable.")
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if exc_type is None:
            # Success!
            if self.state == "HALF_OPEN":
                logger.info(f"Circuit breaker {self.name}: Recovery successful (CLOSED)")
                self.state = "CLOSED"
                self.failures = 0
        else:
            # Failure
            self.failures += 1
            self.last_failure_time = time.time()
            
            if self.failures >= self.failure_threshold:
                if self.state != "OPEN":
                    logger.error(
                        f"Circuit breaker {self.name}: Threshold reached (OPEN). "
                        f"Will retry in {self.timeout}s"
                    )
                self.state = "OPEN"
        
        # Don't suppress exception
        return False


# Example usage
if __name__ == "__main__":
    """
    Demonstrate error handling patterns.
    """
    
    # Example 1: Retry decorator
    @with_retry(max_retries=3)
    def flaky_api_call():
        """Simulates an API that fails sometimes."""
        import random
        if random.random() < 0.6:  # 60% failure rate
            raise requests.exceptions.Timeout("Simulated timeout")
        return {"data": "success"}
    
    print("Testing retry logic...")
    try:
        result = flaky_api_call()
        print(f"✅ Success: {result}")
    except Exception as e:
        print(f"❌ Failed after retries: {e}")
    
    # Example 2: Circuit breaker
    print("\nTesting circuit breaker...")
    breaker = CircuitBreaker(failure_threshold=3, timeout=5, name="TestAPI")
    
    for i in range(10):
        try:
            with breaker:
                # Simulate failing service
                if i < 7:
                    raise requests.exceptions.ConnectionError("Service down")
                print(f"Request {i + 1}: Success!")
        except APIError as e:
            print(f"Request {i + 1}: {e}")
        
        time.sleep(0.5)
```

---

## Testing API Integrations

### Testing Strategy

**Test Pyramid for API Integrations:**

```
           /\
          /  \
         / E2E\     End-to-End: Full integration (slow, few)
        /______\
       /        \
      /Integration\  Integration: Real API calls (medium, some)
     /____________\
    /              \
   /  Unit Tests    \  Unit: Mocked responses (fast, many)
  /__________________\
```

**Testing Levels:**

1. **Unit Tests (Majority)**
   - Mock API responses
   - Test parsing logic
   - Test error handling
   - Fast, run frequently

2. **Integration Tests (Some)**
   - Real API calls to demo environments
   - Test authentication
   - Test data flow
   - Slower, run before deployment

3. **End-to-End Tests (Few)**
   - Full system test
   - Real data through entire pipeline
   - Slowest, run before major releases

### Unit Test Examples

```python
# tests/api_connectors/test_kalshi_client.py

"""
Unit tests for Kalshi API client.

These tests use MOCKED responses (no real API calls).
This makes them:
1. Fast (milliseconds)
2. Reliable (no network dependencies)
3. Repeatable (same result every time)

Educational Notes:
------------------
Mocking: Creating fake objects that behave like real ones.

Why mock?
- Test without API keys
- Test error conditions (hard to trigger in real API)
- Test edge cases (unusual data)
- No rate limits
- No cost
- Instant results

When NOT to mock:
- Testing authentication (need real API)
- Testing actual data format (need real responses)
- Integration tests (testing real connections)

We'll do BOTH mocked (unit) and real (integration) tests!
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal
import requests

# Import our client
from api_connectors.kalshi_client import KalshiClient
from api_connectors.kalshi_auth import KalshiAuth


class TestKalshiAuth:
    """
    Test RSA-PSS authentication.
    
    Note: We CAN'T fully mock RSA signatures (they're cryptographically complex).
    But we can test the structure and flow.
    """
    
    @patch('api_connectors.kalshi_auth.load_private_key')
    def test_get_headers_structure(self, mock_load_key):
        """Test that headers have correct structure."""
        # Mock the private key
        mock_key = Mock()
        mock_load_key.return_value = mock_key
        
        # Mock the signature generation
        mock_key.sign.return_value = b'fake_signature_bytes'
        
        auth = KalshiAuth(api_key="test-key", private_key_path="fake.pem")
        headers = auth.get_headers(method="GET", path="/test")
        
        # Verify header structure
        assert 'KALSHI-ACCESS-KEY' in headers
        assert 'KALSHI-ACCESS-TIMESTAMP' in headers
        assert 'KALSHI-ACCESS-SIGNATURE' in headers
        assert headers['KALSHI-ACCESS-KEY'] == "test-key"
        assert headers['Content-Type'] == 'application/json'
    
    def test_signature_message_format(self):
        """Test that signature message is constructed correctly."""
        # This tests the MESSAGE format, not the actual signature
        from api_connectors.kalshi_auth import generate_signature
        
        # We can test that the message gets formed correctly
        # by mocking just the signing part
        with patch('cryptography.hazmat.primitives.asymmetric.rsa.RSAPrivateKey') as mock_key:
            mock_key_instance = Mock()
            mock_key_instance.sign.return_value = b'signature'
            
            # Message should be: timestamp + METHOD (uppercase) + path
            # Example: "1729123456789GET/trade-api/v2/markets"


class TestKalshiClient:
    """Test Kalshi API client methods."""
    
    @pytest.fixture
    def mock_client(self):
        """Create a Kalshi client with mocked authentication."""
        with patch.dict('os.environ', {
            'KALSHI_DEMO_KEY_ID': 'test-key',
            'KALSHI_DEMO_KEYFILE': 'test.pem'
        }):
            with patch('api_connectors.kalshi_client.KalshiAuth'):
                client = KalshiClient(environment="demo")
                return client
    
    def test_get_markets_parses_decimals(self, mock_client):
        """Test that market prices are converted to Decimal."""
        # Mock the API response
        mock_response = {
            "markets": [
                {
                    "ticker": "TEST-YES",
                    "yes_bid": 0.65,
                    "yes_ask": 0.67,
                    "no_bid": 0.33,
                    "no_ask": 0.35,
                    "last_price": 0.66
                }
            ]
        }
        
        with patch.object(mock_client, '_make_request', return_value=mock_response):
            markets = mock_client.get_markets()
            
            # Verify conversion to Decimal
            assert isinstance(markets[0]['yes_bid'], Decimal)
            assert isinstance(markets[0]['yes_ask'], Decimal)
            assert markets[0]['yes_bid'] == Decimal('0.65')
            assert markets[0]['yes_ask'] == Decimal('0.67')
    
    def test_get_markets_filters(self, mock_client):
        """Test that filter parameters are passed correctly."""
        mock_response = {"markets": []}
        
        with patch.object(mock_client, '_make_request', return_value=mock_response) as mock_request:
            mock_client.get_markets(
                series_ticker="KXNFLGAME",
                limit=50,
                cursor="abc123"
            )
            
            # Verify parameters were passed
            call_args = mock_request.call_args
            params = call_args[1]['params']
            
            assert params['series_ticker'] == "KXNFLGAME"
            assert params['limit'] == 50
            assert params['cursor'] == "abc123"
    
    def test_get_balance_returns_decimal(self, mock_client):
        """Test that balance is returned as Decimal."""
        mock_response = {
            "balance": {
                "balance": 1000.50
            }
        }
        
        with patch.object(mock_client, '_make_request', return_value=mock_response):
            balance = mock_client.get_balance()
            
            assert isinstance(balance['balance'], Decimal)
            assert balance['balance'] == Decimal('1000.50')


class TestESPNClient:
    """Test ESPN API client."""
    
    @pytest.fixture
    def client(self):
        """Create ESPN client."""
        from api_connectors.espn_client import ESPNClient
        return ESPNClient()
    
    def test_parse_nfl_games(self, client):
        """Test parsing of ESPN game data."""
        # Sample ESPN response (simplified)
        mock_data = {
            "events": [
                {
                    "id": "401547516",
                    "name": "Kansas City Chiefs at Buffalo Bills",
                    "shortName": "KC @ BUF",
                    "date": "2025-01-16T18:00Z",
                    "competitions": [
                        {
                            "status": {
                                "type": {"name": "STATUS_IN_PROGRESS"},
                                "period": 4,
                                "displayClock": "2:45"
                            },
                            "competitors": [
                                {
                                    "homeAway": "home",
                                    "team": {
                                        "id": "2",
                                        "displayName": "Buffalo Bills",
                                        "abbreviation": "BUF"
                                    },
                                    "score": "24",
                                    "records": [{"summary": "14-4"}]
                                },
                                {
                                    "homeAway": "away",
                                    "team": {
                                        "id": "12",
                                        "displayName": "Kansas City Chiefs",
                                        "abbreviation": "KC"
                                    },
                                    "score": "27",
                                    "records": [{"summary": "15-3"}]
                                }
                            ],
                            "venue": {
                                "fullName": "Highmark Stadium",
                                "address": {"city": "Orchard Park"}
                            }
                        }
                    ]
                }
            ]
        }
        
        games = client._parse_nfl_games(mock_data)
        
        assert len(games) == 1
        game = games[0]
        
        assert game['id'] == "401547516"
        assert game['home_team'] == "Buffalo Bills"
        assert game['away_team'] == "Kansas City Chiefs"
        assert game['home_score'] == 24
        assert game['away_score'] == 27
        assert game['status'] == "STATUS_IN_PROGRESS"
        assert game['period'] == 4
        assert game['clock'] == "2:45"
        assert game['is_live'] is True
        assert game['lead'] == 3
        assert game['leader'] == "away"


# Integration tests (real API calls)
@pytest.mark.integration
class TestKalshiIntegration:
    """
    Integration tests that make REAL API calls.
    
    Run these with: pytest -m integration
    
    Requirements:
    - Valid KALSHI_DEMO_KEY_ID in .env
    - Valid KALSHI_DEMO_KEYFILE in .env
    - Internet connection
    
    Note: These are slower and depend on external service.
    Run before deployment to verify everything works.
    """
    
    @pytest.fixture
    def client(self):
        """Create real Kalshi client (demo environment)."""
        return KalshiClient(environment="demo")
    
    def test_authentication(self, client):
        """Test that we can authenticate with Kalshi."""
        # Try to get balance (requires authentication)
        balance = client.get_balance()
        
        assert 'balance' in balance
        assert isinstance(balance['balance'], Decimal)
        print(f"✅ Authentication successful. Balance: ${balance['balance']}")
    
    def test_get_markets_real(self, client):
        """Test fetching real markets."""
        markets = client.get_markets(series_ticker="KXNFLGAME", limit=5)
        
        assert isinstance(markets, list)
        assert len(markets) > 0
        
        # Check first market
        market = markets[0]
        assert 'ticker' in market
        assert isinstance(market.get('yes_bid'), (Decimal, type(None)))
        
        print(f"✅ Fetched {len(markets)} NFL markets")


@pytest.mark.integration  
class TestESPNIntegration:
    """Integration tests for ESPN API (real calls)."""
    
    @pytest.fixture
    def client(self):
        from api_connectors.espn_client import ESPNClient
        return ESPNClient()
    
    def test_get_nfl_scoreboard_real(self, client):
        """Test fetching real NFL scoreboard."""
        scoreboard = client.get_nfl_scoreboard()
        
        assert 'games' in scoreboard
        assert isinstance(scoreboard['games'], list)
        
        print(f"✅ Fetched {len(scoreboard['games'])} NFL games")
        
        if scoreboard['games']:
            game = scoreboard['games'][0]
            print(f"   Sample: {game['away_team']} @ {game['home_team']}")


# Run tests
if __name__ == "__main__":
    """
    Run test suite.
    
    Commands:
        # Run all tests
        pytest
        
        # Run only unit tests (fast)
        pytest -m "not integration"
        
        # Run only integration tests
        pytest -m integration
        
        # Run with verbose output
        pytest -v
        
        # Run specific test file
        pytest tests/api_connectors/test_kalshi_client.py
    """
    pytest.main([__file__, "-v"])
```

---

## Phase Implementation Roadmap

### Phase 1: Kalshi Integration (Weeks 1-6)

**Goal:** Get Kalshi API working with authentication, market data fetching, and basic account management.

**Week 1-2: Authentication**
- [ ] Implement RSA-PSS signature generation
- [ ] Test authentication with demo environment
- [ ] Implement token refresh logic (30-minute expiry)
- [ ] Add environment variable management

**Week 3-4: Market Data**
- [ ] Implement get_markets() with pagination
- [ ] Implement get_series() and get_events()
- [ ] Add Decimal price parsing
- [ ] Test with NFL markets

**Week 5-6: Account Management**
- [ ] Implement get_balance()
- [ ] Implement get_positions()
- [ ] Implement get_fills() (trade history)
- [ ] Write comprehensive unit tests

**Success Criteria:**
- ✅ Can authenticate with Kalshi demo
- ✅ Can fetch NFL markets with correct Decimal prices
- ✅ Can retrieve account balance and positions
- ✅ All tests passing (>80% coverage)

---

### Phase 2: Live Game Data (Weeks 7-12)

**Goal:** Integrate ESPN and Weather APIs for real-time game tracking.

**Week 7-8: ESPN Integration**
- [ ] Implement NFL scoreboard endpoint
- [ ] Implement NCAAF scoreboard endpoint
- [ ] Test game data parsing
- [ ] Set up 15-second polling during live games

**Week 9-10: Weather Integration**
- [ ] Set up OpenWeatherMap account
- [ ] Implement stadium coordinates database
- [ ] Implement weather fetching
- [ ] Implement game impact assessment

**Week 11: Balldontlie Backup**
- [ ] Implement Balldontlie client
- [ ] Add fallback logic (ESPN fails → Balldontlie)
- [ ] Test rate limiting (5 req/min)

**Week 12: Integration & Testing**
- [ ] Link game data to Kalshi markets
- [ ] Test full data pipeline
- [ ] Performance optimization
- [ ] Integration tests

**Success Criteria:**
- ✅ Getting live NFL scores every 15 seconds
- ✅ Weather data for all NFL stadiums
- ✅ Automatic fallback if ESPN fails
- ✅ Can match ESPN games to Kalshi markets

---

### Phase 3-4: Odds Calculation & Trading (Weeks 13-24)

*[Covered in other documentation: DEVELOPMENT_PHASES.md]*

---

## Common Pitfalls & Solutions

### Pitfall 1: Using float for Prices

❌ **Wrong:**
```python
price = 0.65
profit = price * 100  # 64.99999999999999 (WTF?)
```

✅ **Right:**
```python
from decimal import Decimal
price = Decimal('0.65')
profit = price * 100  # Exactly 65.00
```

**Why:** Floating point math is imprecise. Decimal is exact.

---

### Pitfall 2: Not Handling Rate Limits

❌ **Wrong:**
```python
for market in markets:
    price = api.get_price(market)  # 💥 Rate limited after 5!
```

✅ **Right:**
```python
rate_limiter = RateLimiter(5, 60)
for market in markets:
    rate_limiter.wait()
    price = api.get_price(market)
```

---

### Pitfall 3: Ignoring Errors

❌ **Wrong:**
```python
try:
    data = api.get_markets()
except:
    pass  # Silent failure - you'll never know what went wrong!
```

✅ **Right:**
```python
try:
    data = api.get_markets()
except RateLimitError as e:
    logger.warning(f"Rate limited: {e}. Waiting...")
    time.sleep(60)
except AuthenticationError as e:
    logger.error(f"Auth failed: {e}")
    send_alert("Kalshi credentials invalid!")
except APIError as e:
    logger.error(f"API error: {e}")
    # Use cached data as fallback
```

---

### Pitfall 4: Hardcoding Stadium Names

❌ **Wrong:**
```python
if stadium == "Lambeau Field":  # Breaks if ESPN uses "Lambeau"
    get_weather()
```

✅ **Right:**
```python
# Fuzzy matching
stadium_normalized = stadium.lower().strip()
if "lambeau" in stadium_normalized:
    get_weather()
```

---

### Pitfall 5: No Timeout on Requests

❌ **Wrong:**
```python
response = requests.get(url)  # Hangs forever if server doesn't respond
```

✅ **Right:**
```python
response = requests.get(url, timeout=10)  # Fails after 10 seconds
```

---

## Summary: Best Practices Checklist

✅ **Authentication:**
- [ ] RSA-PSS for Kalshi (not HMAC)
- [ ] Store keys in .env, never in code
- [ ] Separate demo and prod credentials

✅ **Price Handling:**
- [ ] Always use Decimal, never float
- [ ] Parse `*_dollars` fields from Kalshi
- [ ] Validate prices are in valid range (0.00-1.00)

✅ **API Calls:**
- [ ] Always set timeouts
- [ ] Implement rate limiting
- [ ] Use exponential backoff for retries
- [ ] Add circuit breakers for reliability

✅ **Error Handling:**
- [ ] Catch specific exceptions, not bare `except:`
- [ ] Log all errors with context
- [ ] Have fallback strategies
- [ ] Alert on critical failures

✅ **Testing:**
- [ ] Unit tests with mocked responses (fast)
- [ ] Integration tests with real APIs (before deployment)
- [ ] >80% code coverage
- [ ] Test error conditions, not just happy path

✅ **Data Quality:**
- [ ] Validate all API responses
- [ ] Handle missing fields gracefully
- [ ] Cross-check data between sources
- [ ] Alert on stale data

---

## Related Documents

- **KALSHI_DECIMAL_PRICING_CHEAT_SHEET_V1.0.md** - Critical decimal pricing reference
- **MASTER_REQUIREMENTS_V2.1.md** - High-level API requirements
- **DATABASE_SCHEMA_SUMMARY_V1.1.md** - How to store API data
- **ENVIRONMENT_CHECKLIST_V1.1.md** - Setting up API credentials
- **PHASE_1_TASK_PLAN_V1.0.md** - Implementation tasks and timeline
- **DEVELOPMENT_PHASES_V1.1.md** - Complete roadmap through Phase 10

---

## Changelog

**v2.0 (2025-10-16):**
- 🔴 **MAJOR CORRECTION**: Fixed Kalshi authentication (HMAC-SHA256 → RSA-PSS)
  - Complete rewrite of authentication section
  - Added extensive educational docstrings explaining RSA-PSS
  - Added code examples with cryptography library
- ✅ **EXPANDED**: ESPN API section
  - Added comprehensive NFL/NCAAF/NBA examples
  - Included game state parsing
  - Added live monitoring examples
  - Extensive docstrings explaining sports data
- ✅ **EXPANDED**: Balldontlie API section
  - Rate limiting details and code
  - Free vs paid tier comparison
  - Backup strategy documentation
- ✅ **NEW**: Weather API section (OpenWeatherMap)
  - Stadium coordinates database (NFL + NCAAF)
  - Game impact assessment algorithm
  - Weather adjustment methodology
  - Research-backed scoring impacts
- ✅ **NEW**: Rate limiting section
  - Token bucket algorithm implementation
  - Exponential backoff for retries
  - Rate limiter class with examples
- ✅ **NEW**: Error handling section
  - Comprehensive error types
  - Retry decorators
  - Circuit breaker pattern
  - Production-ready examples
- ✅ **NEW**: Testing section
  - Unit test examples with mocking
  - Integration test patterns
  - pytest configuration
- ✅ **NEW**: Best practices checklist
- ✅ **NEW**: Common pitfalls and solutions
- ✅ All code examples include extensive educational docstrings

**v1.0 (2025-10-15):**
- Initial creation
- Kalshi API basics (incorrect HMAC auth)
- Basic ESPN and Balldontlie references
- No weather API

---

**END OF API_INTEGRATION_GUIDE_V2.0.md**