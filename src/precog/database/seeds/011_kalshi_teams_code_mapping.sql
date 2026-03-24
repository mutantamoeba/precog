-- Seed Data: Kalshi Platform Team Codes
-- Date: 2026-03-23
-- Purpose: Set kalshi_team_code for teams where Kalshi uses a different code
--          than the canonical team_code (ESPN). For most teams, Kalshi uses
--          the same code as ESPN, so only mismatches need explicit mapping.
-- Related: Issue #462 (Event-to-game matching)

-- ============================================================================
-- BACKGROUND: Kalshi Team Code Mapping
-- ============================================================================
-- Kalshi event tickers embed team codes: "KXNFLGAME-26JAN18HOUNE"
-- Most Kalshi codes match ESPN codes (HOU, NE, BUF, etc.)
-- Known mismatches (verified from live Kalshi API data):
--   NFL: JAC (Kalshi) vs JAX (ESPN), LA (Kalshi) vs LAR (ESPN)
--   NBA: None confirmed yet (all match)
--   NHL: Not yet verified
--
-- Strategy: Only set kalshi_team_code where it DIFFERS from team_code.
-- The matching module treats NULL kalshi_team_code as "same as team_code".

-- ============================================================================
-- NFL TEAM CODE MISMATCHES
-- ============================================================================
-- Jacksonville: Kalshi uses JAC, ESPN/DB uses JAX
UPDATE teams SET kalshi_team_code = 'JAC'
WHERE team_code = 'JAX' AND league = 'nfl';

-- LA Rams: Kalshi uses LA, ESPN/DB uses LAR
UPDATE teams SET kalshi_team_code = 'LA'
WHERE team_code = 'LAR' AND league = 'nfl';

-- New Orleans: Kalshi uses NO in some tickers, ESPN/DB uses NO — same, skip.
-- Green Bay: Kalshi uses GB, ESPN/DB uses GB — same, skip.

-- ============================================================================
-- NBA TEAM CODE MISMATCHES
-- ============================================================================
-- No confirmed mismatches. All NBA Kalshi codes match ESPN team_code.
-- If mismatches are discovered from live data, add UPDATE statements here.

-- ============================================================================
-- NHL TEAM CODE MISMATCHES
-- ============================================================================
-- Not yet verified against live Kalshi NHL data.
-- Add UPDATE statements here when mismatches are confirmed.

-- ============================================================================
-- VERIFICATION
-- ============================================================================

DO $$
DECLARE
    jax_code TEXT;
    lar_code TEXT;
BEGIN
    -- Verify JAX team got JAC Kalshi code
    SELECT kalshi_team_code INTO jax_code
    FROM teams WHERE team_code = 'JAX' AND league = 'nfl';

    IF jax_code IS DISTINCT FROM 'JAC' THEN
        RAISE WARNING 'JAX kalshi_team_code not set (team may not exist yet): expected JAC, got %', COALESCE(jax_code, 'NULL');
    END IF;

    -- Verify LAR team got LA Kalshi code
    SELECT kalshi_team_code INTO lar_code
    FROM teams WHERE team_code = 'LAR' AND league = 'nfl';

    IF lar_code IS DISTINCT FROM 'LA' THEN
        RAISE WARNING 'LAR kalshi_team_code not set (team may not exist yet): expected LA, got %', COALESCE(lar_code, 'NULL');
    END IF;

    RAISE NOTICE 'Kalshi team code seed complete. Mismatches set: JAX->JAC, LAR->LA';
END $$;
