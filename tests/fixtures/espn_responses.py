"""
ESPN API response fixtures for testing.

This module provides realistic sample responses from the ESPN public API for:
- NFL Scoreboard endpoint
- NCAAF Scoreboard endpoint
- Various game states (pre-game, in-progress, final)
- Error responses

ESPN API Endpoints:
- NFL: https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard
- NCAAF: https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard

Usage in tests:
    from tests.fixtures.espn_responses import ESPN_NFL_SCOREBOARD_LIVE

    @mock.patch('requests.Session.get')
    def test_fetch_live_games(mock_get):
        mock_get.return_value.json.return_value = ESPN_NFL_SCOREBOARD_LIVE
        # Test implementation

Reference: docs/testing/PHASE_2_TEST_PLAN_V1.0.md Section 2.1
"""


# =============================================================================
# ESPN NFL Scoreboard - Live Game
# =============================================================================

ESPN_NFL_SCOREBOARD_LIVE = {
    "leagues": [
        {
            "id": "28",
            "uid": "s:20~l:28",
            "name": "National Football League",
            "abbreviation": "NFL",
            "slug": "nfl",
            "season": {
                "year": 2025,
                "type": 2,
                "name": "Regular Season",
                "displayName": "2025 Regular Season",
            },
        }
    ],
    "season": {"type": 2, "year": 2025},
    "week": {"number": 15},
    "events": [
        {
            "id": "401547417",
            "uid": "s:20~l:28~e:401547417",
            "date": "2025-12-15T18:00Z",
            "name": "Kansas City Chiefs at Buffalo Bills",
            "shortName": "KC @ BUF",
            "season": {"year": 2025, "type": 2, "slug": "regular-season"},
            "week": {"number": 15},
            "competitions": [
                {
                    "id": "401547417",
                    "uid": "s:20~l:28~e:401547417~c:401547417",
                    "date": "2025-12-15T18:00Z",
                    "attendance": 71608,
                    "type": {"id": "1", "abbreviation": "STD"},
                    "timeValid": True,
                    "neutralSite": False,
                    "conferenceCompetition": False,
                    "playByPlayAvailable": True,
                    "recent": True,
                    "venue": {
                        "id": "3883",
                        "fullName": "Highmark Stadium",
                        "address": {"city": "Orchard Park", "state": "NY"},
                        "capacity": 71608,
                        "indoor": False,
                    },
                    "competitors": [
                        {
                            "id": "2",
                            "uid": "s:20~l:28~t:2",
                            "type": "team",
                            "order": 0,
                            "homeAway": "home",
                            "winner": False,
                            "team": {
                                "id": "2",
                                "uid": "s:20~l:28~t:2",
                                "location": "Buffalo",
                                "name": "Bills",
                                "abbreviation": "BUF",
                                "displayName": "Buffalo Bills",
                                "shortDisplayName": "Bills",
                                "color": "00338D",
                                "alternateColor": "c60c30",
                                "logo": "https://a.espncdn.com/i/teamlogos/nfl/500/buf.png",
                            },
                            "score": "24",
                            "linescores": [
                                {"value": 7},
                                {"value": 10},
                                {"value": 7},
                                {"value": 0},
                            ],
                            "statistics": [],
                            "records": [
                                {"name": "overall", "summary": "11-3"},
                                {"name": "home", "summary": "6-1"},
                            ],
                        },
                        {
                            "id": "12",
                            "uid": "s:20~l:28~t:12",
                            "type": "team",
                            "order": 1,
                            "homeAway": "away",
                            "winner": False,
                            "team": {
                                "id": "12",
                                "uid": "s:20~l:28~t:12",
                                "location": "Kansas City",
                                "name": "Chiefs",
                                "abbreviation": "KC",
                                "displayName": "Kansas City Chiefs",
                                "shortDisplayName": "Chiefs",
                                "color": "E31837",
                                "alternateColor": "ffb612",
                                "logo": "https://a.espncdn.com/i/teamlogos/nfl/500/kc.png",
                            },
                            "score": "21",
                            "linescores": [
                                {"value": 7},
                                {"value": 7},
                                {"value": 7},
                                {"value": 0},
                            ],
                            "statistics": [],
                            "records": [
                                {"name": "overall", "summary": "12-2"},
                                {"name": "away", "summary": "6-1"},
                            ],
                        },
                    ],
                    "status": {
                        "clock": 485.0,  # 8:05 remaining in seconds
                        "displayClock": "8:05",
                        "period": 4,
                        "type": {
                            "id": "2",
                            "name": "STATUS_IN_PROGRESS",
                            "state": "in",
                            "completed": False,
                            "description": "In Progress",
                            "detail": "4th - 8:05",
                            "shortDetail": "4th - 8:05",
                        },
                    },
                    "broadcasts": [{"market": "national", "names": ["CBS"]}],
                    "situation": {
                        "lastPlay": {
                            "id": "4015474171234",
                            "type": {"id": "24", "text": "Pass Reception"},
                            "text": "Patrick Mahomes pass complete to Travis Kelce for 15 yards",
                            "scoreValue": 0,
                            "athletesInvolved": [
                                {"id": "3139477", "displayName": "Patrick Mahomes"},
                                {"id": "2533031", "displayName": "Travis Kelce"},
                            ],
                        },
                        "down": 1,
                        "yardLine": 35,
                        "distance": 10,
                        "downDistanceText": "1st & 10 at BUF 35",
                        "shortDownDistanceText": "1st & 10",
                        "possessionText": "KC Ball",
                        "isRedZone": False,
                        "homeTimeouts": 2,
                        "awayTimeouts": 1,
                        "possession": "12",  # KC has possession
                    },
                }
            ],
            "status": {
                "clock": 485.0,
                "displayClock": "8:05",
                "period": 4,
                "type": {
                    "id": "2",
                    "name": "STATUS_IN_PROGRESS",
                    "state": "in",
                    "completed": False,
                    "description": "In Progress",
                    "detail": "4th - 8:05",
                    "shortDetail": "4th - 8:05",
                },
            },
        },
        # Second game - also in progress
        {
            "id": "401547418",
            "uid": "s:20~l:28~e:401547418",
            "date": "2025-12-15T21:25Z",
            "name": "Philadelphia Eagles at Dallas Cowboys",
            "shortName": "PHI @ DAL",
            "season": {"year": 2025, "type": 2, "slug": "regular-season"},
            "week": {"number": 15},
            "competitions": [
                {
                    "id": "401547418",
                    "uid": "s:20~l:28~e:401547418~c:401547418",
                    "date": "2025-12-15T21:25Z",
                    "attendance": 93596,
                    "type": {"id": "1", "abbreviation": "STD"},
                    "timeValid": True,
                    "neutralSite": False,
                    "conferenceCompetition": False,
                    "playByPlayAvailable": True,
                    "recent": True,
                    "venue": {
                        "id": "3687",
                        "fullName": "AT&T Stadium",
                        "address": {"city": "Arlington", "state": "TX"},
                        "capacity": 93596,
                        "indoor": True,
                    },
                    "competitors": [
                        {
                            "id": "6",
                            "uid": "s:20~l:28~t:6",
                            "type": "team",
                            "order": 0,
                            "homeAway": "home",
                            "winner": False,
                            "team": {
                                "id": "6",
                                "uid": "s:20~l:28~t:6",
                                "location": "Dallas",
                                "name": "Cowboys",
                                "abbreviation": "DAL",
                                "displayName": "Dallas Cowboys",
                                "shortDisplayName": "Cowboys",
                                "color": "041E42",
                                "alternateColor": "869397",
                                "logo": "https://a.espncdn.com/i/teamlogos/nfl/500/dal.png",
                            },
                            "score": "14",
                            "linescores": [
                                {"value": 7},
                                {"value": 7},
                                {"value": 0},
                            ],
                            "statistics": [],
                            "records": [
                                {"name": "overall", "summary": "6-8"},
                                {"name": "home", "summary": "4-3"},
                            ],
                        },
                        {
                            "id": "21",
                            "uid": "s:20~l:28~t:21",
                            "type": "team",
                            "order": 1,
                            "homeAway": "away",
                            "winner": False,
                            "team": {
                                "id": "21",
                                "uid": "s:20~l:28~t:21",
                                "location": "Philadelphia",
                                "name": "Eagles",
                                "abbreviation": "PHI",
                                "displayName": "Philadelphia Eagles",
                                "shortDisplayName": "Eagles",
                                "color": "004C54",
                                "alternateColor": "a5acaf",
                                "logo": "https://a.espncdn.com/i/teamlogos/nfl/500/phi.png",
                            },
                            "score": "17",
                            "linescores": [
                                {"value": 10},
                                {"value": 0},
                                {"value": 7},
                            ],
                            "statistics": [],
                            "records": [
                                {"name": "overall", "summary": "11-3"},
                                {"name": "away", "summary": "5-2"},
                            ],
                        },
                    ],
                    "status": {
                        "clock": 120.0,  # 2:00 remaining
                        "displayClock": "2:00",
                        "period": 3,
                        "type": {
                            "id": "2",
                            "name": "STATUS_IN_PROGRESS",
                            "state": "in",
                            "completed": False,
                            "description": "In Progress",
                            "detail": "3rd - 2:00",
                            "shortDetail": "3rd - 2:00",
                        },
                    },
                    "broadcasts": [{"market": "national", "names": ["FOX"]}],
                    "situation": {
                        "lastPlay": {
                            "id": "4015474181234",
                            "type": {"id": "68", "text": "Rush"},
                            "text": "Saquon Barkley rush for 8 yards",
                            "scoreValue": 0,
                        },
                        "down": 2,
                        "yardLine": 45,
                        "distance": 2,
                        "downDistanceText": "2nd & 2 at DAL 45",
                        "shortDownDistanceText": "2nd & 2",
                        "possessionText": "PHI Ball",
                        "isRedZone": False,
                        "homeTimeouts": 3,
                        "awayTimeouts": 2,
                        "possession": "21",  # PHI has possession
                    },
                }
            ],
            "status": {
                "clock": 120.0,
                "displayClock": "2:00",
                "period": 3,
                "type": {
                    "id": "2",
                    "name": "STATUS_IN_PROGRESS",
                    "state": "in",
                    "completed": False,
                    "description": "In Progress",
                    "detail": "3rd - 2:00",
                    "shortDetail": "3rd - 2:00",
                },
            },
        },
    ],
}


# =============================================================================
# ESPN NFL Scoreboard - Pre-game
# =============================================================================

ESPN_NFL_SCOREBOARD_PREGAME = {
    "leagues": [
        {
            "id": "28",
            "uid": "s:20~l:28",
            "name": "National Football League",
            "abbreviation": "NFL",
            "slug": "nfl",
            "season": {"year": 2025, "type": 2},
        }
    ],
    "season": {"type": 2, "year": 2025},
    "week": {"number": 15},
    "events": [
        {
            "id": "401547419",
            "uid": "s:20~l:28~e:401547419",
            "date": "2025-12-16T01:20Z",
            "name": "San Francisco 49ers at Seattle Seahawks",
            "shortName": "SF @ SEA",
            "season": {"year": 2025, "type": 2, "slug": "regular-season"},
            "week": {"number": 15},
            "competitions": [
                {
                    "id": "401547419",
                    "uid": "s:20~l:28~e:401547419~c:401547419",
                    "date": "2025-12-16T01:20Z",
                    "attendance": 0,
                    "type": {"id": "1", "abbreviation": "STD"},
                    "timeValid": True,
                    "neutralSite": False,
                    "conferenceCompetition": False,
                    "playByPlayAvailable": False,
                    "recent": False,
                    "venue": {
                        "id": "3647",
                        "fullName": "Lumen Field",
                        "address": {"city": "Seattle", "state": "WA"},
                        "capacity": 68740,
                        "indoor": False,
                    },
                    "competitors": [
                        {
                            "id": "26",
                            "uid": "s:20~l:28~t:26",
                            "type": "team",
                            "order": 0,
                            "homeAway": "home",
                            "winner": False,
                            "team": {
                                "id": "26",
                                "uid": "s:20~l:28~t:26",
                                "location": "Seattle",
                                "name": "Seahawks",
                                "abbreviation": "SEA",
                                "displayName": "Seattle Seahawks",
                                "shortDisplayName": "Seahawks",
                                "color": "002244",
                                "alternateColor": "69be28",
                                "logo": "https://a.espncdn.com/i/teamlogos/nfl/500/sea.png",
                            },
                            "score": "0",
                            "linescores": [],
                            "statistics": [],
                            "records": [
                                {"name": "overall", "summary": "8-6"},
                                {"name": "home", "summary": "4-3"},
                            ],
                        },
                        {
                            "id": "25",
                            "uid": "s:20~l:28~t:25",
                            "type": "team",
                            "order": 1,
                            "homeAway": "away",
                            "winner": False,
                            "team": {
                                "id": "25",
                                "uid": "s:20~l:28~t:25",
                                "location": "San Francisco",
                                "name": "49ers",
                                "abbreviation": "SF",
                                "displayName": "San Francisco 49ers",
                                "shortDisplayName": "49ers",
                                "color": "AA0000",
                                "alternateColor": "b3995d",
                                "logo": "https://a.espncdn.com/i/teamlogos/nfl/500/sf.png",
                            },
                            "score": "0",
                            "linescores": [],
                            "statistics": [],
                            "records": [
                                {"name": "overall", "summary": "7-7"},
                                {"name": "away", "summary": "3-4"},
                            ],
                        },
                    ],
                    "status": {
                        "clock": 0.0,
                        "displayClock": "0:00",
                        "period": 0,
                        "type": {
                            "id": "1",
                            "name": "STATUS_SCHEDULED",
                            "state": "pre",
                            "completed": False,
                            "description": "Scheduled",
                            "detail": "Sun, December 15th at 8:20 PM EST",
                            "shortDetail": "12/15 - 8:20 PM EST",
                        },
                    },
                    "broadcasts": [{"market": "national", "names": ["NBC"]}],
                }
            ],
            "status": {
                "clock": 0.0,
                "displayClock": "0:00",
                "period": 0,
                "type": {
                    "id": "1",
                    "name": "STATUS_SCHEDULED",
                    "state": "pre",
                    "completed": False,
                    "description": "Scheduled",
                    "detail": "Sun, December 15th at 8:20 PM EST",
                    "shortDetail": "12/15 - 8:20 PM EST",
                },
            },
        }
    ],
}


# =============================================================================
# ESPN NFL Scoreboard - Final (Completed Game)
# =============================================================================

ESPN_NFL_SCOREBOARD_FINAL = {
    "leagues": [
        {
            "id": "28",
            "uid": "s:20~l:28",
            "name": "National Football League",
            "abbreviation": "NFL",
            "slug": "nfl",
            "season": {"year": 2025, "type": 2},
        }
    ],
    "season": {"type": 2, "year": 2025},
    "week": {"number": 14},
    "events": [
        {
            "id": "401547410",
            "uid": "s:20~l:28~e:401547410",
            "date": "2025-12-08T18:00Z",
            "name": "Baltimore Ravens at Pittsburgh Steelers",
            "shortName": "BAL @ PIT",
            "season": {"year": 2025, "type": 2, "slug": "regular-season"},
            "week": {"number": 14},
            "competitions": [
                {
                    "id": "401547410",
                    "uid": "s:20~l:28~e:401547410~c:401547410",
                    "date": "2025-12-08T18:00Z",
                    "attendance": 68400,
                    "type": {"id": "1", "abbreviation": "STD"},
                    "timeValid": True,
                    "neutralSite": False,
                    "conferenceCompetition": False,
                    "playByPlayAvailable": True,
                    "recent": False,
                    "venue": {
                        "id": "3860",
                        "fullName": "Acrisure Stadium",
                        "address": {"city": "Pittsburgh", "state": "PA"},
                        "capacity": 68400,
                        "indoor": False,
                    },
                    "competitors": [
                        {
                            "id": "23",
                            "uid": "s:20~l:28~t:23",
                            "type": "team",
                            "order": 0,
                            "homeAway": "home",
                            "winner": False,
                            "team": {
                                "id": "23",
                                "uid": "s:20~l:28~t:23",
                                "location": "Pittsburgh",
                                "name": "Steelers",
                                "abbreviation": "PIT",
                                "displayName": "Pittsburgh Steelers",
                                "shortDisplayName": "Steelers",
                                "color": "FFB612",
                                "alternateColor": "101820",
                                "logo": "https://a.espncdn.com/i/teamlogos/nfl/500/pit.png",
                            },
                            "score": "20",
                            "linescores": [
                                {"value": 7},
                                {"value": 3},
                                {"value": 7},
                                {"value": 3},
                            ],
                            "statistics": [],
                            "records": [
                                {"name": "overall", "summary": "10-4"},
                                {"name": "home", "summary": "5-2"},
                            ],
                        },
                        {
                            "id": "33",
                            "uid": "s:20~l:28~t:33",
                            "type": "team",
                            "order": 1,
                            "homeAway": "away",
                            "winner": True,
                            "team": {
                                "id": "33",
                                "uid": "s:20~l:28~t:33",
                                "location": "Baltimore",
                                "name": "Ravens",
                                "abbreviation": "BAL",
                                "displayName": "Baltimore Ravens",
                                "shortDisplayName": "Ravens",
                                "color": "241773",
                                "alternateColor": "9e7c0c",
                                "logo": "https://a.espncdn.com/i/teamlogos/nfl/500/bal.png",
                            },
                            "score": "27",
                            "linescores": [
                                {"value": 10},
                                {"value": 7},
                                {"value": 3},
                                {"value": 7},
                            ],
                            "statistics": [],
                            "records": [
                                {"name": "overall", "summary": "9-5"},
                                {"name": "away", "summary": "4-3"},
                            ],
                        },
                    ],
                    "status": {
                        "clock": 0.0,
                        "displayClock": "0:00",
                        "period": 4,
                        "type": {
                            "id": "3",
                            "name": "STATUS_FINAL",
                            "state": "post",
                            "completed": True,
                            "description": "Final",
                            "detail": "Final",
                            "shortDetail": "Final",
                        },
                    },
                    "broadcasts": [{"market": "national", "names": ["CBS"]}],
                }
            ],
            "status": {
                "clock": 0.0,
                "displayClock": "0:00",
                "period": 4,
                "type": {
                    "id": "3",
                    "name": "STATUS_FINAL",
                    "state": "post",
                    "completed": True,
                    "description": "Final",
                    "detail": "Final",
                    "shortDetail": "Final",
                },
            },
        }
    ],
}


# =============================================================================
# ESPN NFL Scoreboard - Halftime
# =============================================================================

ESPN_NFL_SCOREBOARD_HALFTIME = {
    "leagues": [
        {
            "id": "28",
            "uid": "s:20~l:28",
            "name": "National Football League",
            "abbreviation": "NFL",
            "slug": "nfl",
        }
    ],
    "season": {"type": 2, "year": 2025},
    "week": {"number": 15},
    "events": [
        {
            "id": "401547420",
            "uid": "s:20~l:28~e:401547420",
            "date": "2025-12-15T18:00Z",
            "name": "Miami Dolphins at New York Jets",
            "shortName": "MIA @ NYJ",
            "season": {"year": 2025, "type": 2, "slug": "regular-season"},
            "week": {"number": 15},
            "competitions": [
                {
                    "id": "401547420",
                    "uid": "s:20~l:28~e:401547420~c:401547420",
                    "date": "2025-12-15T18:00Z",
                    "attendance": 82500,
                    "type": {"id": "1", "abbreviation": "STD"},
                    "timeValid": True,
                    "neutralSite": False,
                    "conferenceCompetition": False,
                    "playByPlayAvailable": True,
                    "recent": True,
                    "venue": {
                        "id": "3839",
                        "fullName": "MetLife Stadium",
                        "address": {"city": "East Rutherford", "state": "NJ"},
                        "capacity": 82500,
                        "indoor": False,
                    },
                    "competitors": [
                        {
                            "id": "20",
                            "uid": "s:20~l:28~t:20",
                            "type": "team",
                            "order": 0,
                            "homeAway": "home",
                            "winner": False,
                            "team": {
                                "id": "20",
                                "uid": "s:20~l:28~t:20",
                                "location": "New York",
                                "name": "Jets",
                                "abbreviation": "NYJ",
                                "displayName": "New York Jets",
                                "shortDisplayName": "Jets",
                                "color": "125740",
                                "alternateColor": "000000",
                                "logo": "https://a.espncdn.com/i/teamlogos/nfl/500/nyj.png",
                            },
                            "score": "10",
                            "linescores": [
                                {"value": 3},
                                {"value": 7},
                            ],
                            "statistics": [],
                            "records": [
                                {"name": "overall", "summary": "4-10"},
                                {"name": "home", "summary": "2-5"},
                            ],
                        },
                        {
                            "id": "15",
                            "uid": "s:20~l:28~t:15",
                            "type": "team",
                            "order": 1,
                            "homeAway": "away",
                            "winner": False,
                            "team": {
                                "id": "15",
                                "uid": "s:20~l:28~t:15",
                                "location": "Miami",
                                "name": "Dolphins",
                                "abbreviation": "MIA",
                                "displayName": "Miami Dolphins",
                                "shortDisplayName": "Dolphins",
                                "color": "008E97",
                                "alternateColor": "f58220",
                                "logo": "https://a.espncdn.com/i/teamlogos/nfl/500/mia.png",
                            },
                            "score": "14",
                            "linescores": [
                                {"value": 7},
                                {"value": 7},
                            ],
                            "statistics": [],
                            "records": [
                                {"name": "overall", "summary": "6-8"},
                                {"name": "away", "summary": "3-4"},
                            ],
                        },
                    ],
                    "status": {
                        "clock": 0.0,
                        "displayClock": "0:00",
                        "period": 2,
                        "type": {
                            "id": "23",
                            "name": "STATUS_HALFTIME",
                            "state": "in",
                            "completed": False,
                            "description": "Halftime",
                            "detail": "Halftime",
                            "shortDetail": "Halftime",
                        },
                    },
                    "broadcasts": [{"market": "national", "names": ["CBS"]}],
                }
            ],
            "status": {
                "clock": 0.0,
                "displayClock": "0:00",
                "period": 2,
                "type": {
                    "id": "23",
                    "name": "STATUS_HALFTIME",
                    "state": "in",
                    "completed": False,
                    "description": "Halftime",
                    "detail": "Halftime",
                    "shortDetail": "Halftime",
                },
            },
        }
    ],
}


# =============================================================================
# ESPN NFL Scoreboard - Empty (No Games Today)
# =============================================================================

ESPN_NFL_SCOREBOARD_EMPTY = {
    "leagues": [
        {
            "id": "28",
            "uid": "s:20~l:28",
            "name": "National Football League",
            "abbreviation": "NFL",
            "slug": "nfl",
        }
    ],
    "season": {"type": 2, "year": 2025},
    "week": {"number": 15},
    "events": [],
}


# =============================================================================
# ESPN NCAAF Scoreboard - Live Game
# =============================================================================

ESPN_NCAAF_SCOREBOARD_LIVE = {
    "leagues": [
        {
            "id": "23",
            "uid": "s:20~l:23",
            "name": "NCAA - Loss Football",
            "abbreviation": "NCAAF",
            "slug": "college-football",
            "season": {"year": 2025, "type": 2},
        }
    ],
    "season": {"type": 2, "year": 2025},
    "week": {"number": 14},
    "events": [
        {
            "id": "401628501",
            "uid": "s:20~l:23~e:401628501",
            "date": "2025-12-07T20:00Z",
            "name": "Ohio State Buckeyes vs Michigan Wolverines",
            "shortName": "OSU vs MICH",
            "season": {"year": 2025, "type": 2, "slug": "regular-season"},
            "week": {"number": 14},
            "competitions": [
                {
                    "id": "401628501",
                    "uid": "s:20~l:23~e:401628501~c:401628501",
                    "date": "2025-12-07T20:00Z",
                    "attendance": 106572,
                    "type": {"id": "1", "abbreviation": "STD"},
                    "timeValid": True,
                    "neutralSite": False,
                    "conferenceCompetition": True,
                    "playByPlayAvailable": True,
                    "recent": True,
                    "venue": {
                        "id": "3861",
                        "fullName": "Ohio Stadium",
                        "address": {"city": "Columbus", "state": "OH"},
                        "capacity": 106572,
                        "indoor": False,
                    },
                    "competitors": [
                        {
                            "id": "194",
                            "uid": "s:20~l:23~t:194",
                            "type": "team",
                            "order": 0,
                            "homeAway": "home",
                            "winner": False,
                            "team": {
                                "id": "194",
                                "uid": "s:20~l:23~t:194",
                                "location": "Ohio State",
                                "name": "Buckeyes",
                                "abbreviation": "OSU",
                                "displayName": "Ohio State Buckeyes",
                                "shortDisplayName": "Buckeyes",
                                "color": "BB0000",
                                "alternateColor": "666666",
                                "logo": "https://a.espncdn.com/i/teamlogos/ncaa/500/194.png",
                            },
                            "score": "28",
                            "linescores": [
                                {"value": 7},
                                {"value": 14},
                                {"value": 7},
                                {"value": 0},
                            ],
                            "curatedRank": {"current": 2},
                            "statistics": [],
                            "records": [
                                {"name": "overall", "summary": "11-1"},
                                {"name": "home", "summary": "6-0"},
                            ],
                        },
                        {
                            "id": "130",
                            "uid": "s:20~l:23~t:130",
                            "type": "team",
                            "order": 1,
                            "homeAway": "away",
                            "winner": False,
                            "team": {
                                "id": "130",
                                "uid": "s:20~l:23~t:130",
                                "location": "Michigan",
                                "name": "Wolverines",
                                "abbreviation": "MICH",
                                "displayName": "Michigan Wolverines",
                                "shortDisplayName": "Wolverines",
                                "color": "00274C",
                                "alternateColor": "ffcb05",
                                "logo": "https://a.espncdn.com/i/teamlogos/ncaa/500/130.png",
                            },
                            "score": "21",
                            "linescores": [
                                {"value": 7},
                                {"value": 7},
                                {"value": 7},
                                {"value": 0},
                            ],
                            "curatedRank": {"current": 3},
                            "statistics": [],
                            "records": [
                                {"name": "overall", "summary": "11-1"},
                                {"name": "away", "summary": "5-1"},
                            ],
                        },
                    ],
                    "status": {
                        "clock": 600.0,  # 10:00 remaining
                        "displayClock": "10:00",
                        "period": 4,
                        "type": {
                            "id": "2",
                            "name": "STATUS_IN_PROGRESS",
                            "state": "in",
                            "completed": False,
                            "description": "In Progress",
                            "detail": "4th - 10:00",
                            "shortDetail": "4th - 10:00",
                        },
                    },
                    "broadcasts": [{"market": "national", "names": ["FOX"]}],
                    "situation": {
                        "down": 3,
                        "yardLine": 50,
                        "distance": 4,
                        "downDistanceText": "3rd & 4 at 50",
                        "shortDownDistanceText": "3rd & 4",
                        "possessionText": "OSU Ball",
                        "isRedZone": False,
                        "homeTimeouts": 3,
                        "awayTimeouts": 2,
                        "possession": "194",  # OSU has possession
                    },
                }
            ],
            "status": {
                "clock": 600.0,
                "displayClock": "10:00",
                "period": 4,
                "type": {
                    "id": "2",
                    "name": "STATUS_IN_PROGRESS",
                    "state": "in",
                    "completed": False,
                    "description": "In Progress",
                    "detail": "4th - 10:00",
                    "shortDetail": "4th - 10:00",
                },
            },
        }
    ],
}


# =============================================================================
# ESPN Error Responses
# =============================================================================

ESPN_ERROR_404_RESPONSE = {
    "status": 404,
    "error": "Not Found",
    "message": "The requested resource was not found",
}

ESPN_ERROR_500_RESPONSE = {
    "status": 500,
    "error": "Internal Server Error",
    "message": "An unexpected error occurred",
}

ESPN_ERROR_503_RESPONSE = {
    "status": 503,
    "error": "Service Unavailable",
    "message": "Service temporarily unavailable. Please try again later.",
}


# =============================================================================
# Expected Parsed Game States (After Processing)
# =============================================================================

EXPECTED_GAME_STATE_LIVE = {
    "espn_event_id": "401547417",
    "home_team": "BUF",
    "away_team": "KC",
    "home_score": 24,
    "away_score": 21,
    "period": 4,
    "clock_seconds": 485,
    "clock_display": "8:05",
    "game_status": "in_progress",
    "possession": "away",  # KC has the ball
    "down": 1,
    "distance": 10,
    "yard_line": 35,
    "is_red_zone": False,
    "home_timeouts": 2,
    "away_timeouts": 1,
}

EXPECTED_GAME_STATE_PREGAME = {
    "espn_event_id": "401547419",
    "home_team": "SEA",
    "away_team": "SF",
    "home_score": 0,
    "away_score": 0,
    "period": 0,
    "clock_seconds": 0,
    "clock_display": "0:00",
    "game_status": "scheduled",
    "possession": None,
    "down": None,
    "distance": None,
    "yard_line": None,
    "is_red_zone": False,
    "home_timeouts": 3,
    "away_timeouts": 3,
}

EXPECTED_GAME_STATE_FINAL = {
    "espn_event_id": "401547410",
    "home_team": "PIT",
    "away_team": "BAL",
    "home_score": 20,
    "away_score": 27,
    "period": 4,
    "clock_seconds": 0,
    "clock_display": "0:00",
    "game_status": "final",
    "possession": None,
    "down": None,
    "distance": None,
    "yard_line": None,
    "is_red_zone": False,
    "home_timeouts": 0,
    "away_timeouts": 0,
    "winner": "away",  # BAL won
}

EXPECTED_GAME_STATE_HALFTIME = {
    "espn_event_id": "401547420",
    "home_team": "NYJ",
    "away_team": "MIA",
    "home_score": 10,
    "away_score": 14,
    "period": 2,
    "clock_seconds": 0,
    "clock_display": "0:00",
    "game_status": "halftime",
    "possession": None,
    "down": None,
    "distance": None,
    "yard_line": None,
    "is_red_zone": False,
    "home_timeouts": 3,
    "away_timeouts": 3,
}


# =============================================================================
# Edge Cases and Special Scenarios
# =============================================================================

# Overtime game
ESPN_NFL_SCOREBOARD_OVERTIME = {
    "leagues": [{"id": "28", "abbreviation": "NFL"}],
    "season": {"type": 2, "year": 2025},
    "events": [
        {
            "id": "401547421",
            "name": "Detroit Lions at Green Bay Packers",
            "shortName": "DET @ GB",
            "competitions": [
                {
                    "id": "401547421",
                    "competitors": [
                        {
                            "id": "9",
                            "homeAway": "home",
                            "team": {
                                "id": "9",
                                "abbreviation": "GB",
                                "displayName": "Green Bay Packers",
                            },
                            "score": "31",
                            "linescores": [
                                {"value": 7},
                                {"value": 10},
                                {"value": 7},
                                {"value": 7},
                                {"value": 0},  # OT
                            ],
                        },
                        {
                            "id": "8",
                            "homeAway": "away",
                            "team": {
                                "id": "8",
                                "abbreviation": "DET",
                                "displayName": "Detroit Lions",
                            },
                            "score": "31",
                            "linescores": [
                                {"value": 10},
                                {"value": 7},
                                {"value": 7},
                                {"value": 7},
                                {"value": 0},  # OT
                            ],
                        },
                    ],
                    "status": {
                        "clock": 420.0,  # 7:00 remaining
                        "displayClock": "7:00",
                        "period": 5,  # Overtime
                        "type": {
                            "id": "2",
                            "name": "STATUS_IN_PROGRESS",
                            "state": "in",
                            "completed": False,
                            "description": "In Progress",
                            "detail": "OT - 7:00",
                            "shortDetail": "OT - 7:00",
                        },
                    },
                }
            ],
            "status": {
                "period": 5,
                "type": {
                    "state": "in",
                    "completed": False,
                    "detail": "OT - 7:00",
                },
            },
        }
    ],
}

# Red zone situation
ESPN_NFL_SCOREBOARD_REDZONE = {
    "leagues": [{"id": "28", "abbreviation": "NFL"}],
    "season": {"type": 2, "year": 2025},
    "events": [
        {
            "id": "401547422",
            "name": "Las Vegas Raiders at Denver Broncos",
            "shortName": "LV @ DEN",
            "competitions": [
                {
                    "id": "401547422",
                    "competitors": [
                        {
                            "id": "7",
                            "homeAway": "home",
                            "team": {
                                "id": "7",
                                "abbreviation": "DEN",
                                "displayName": "Denver Broncos",
                            },
                            "score": "17",
                        },
                        {
                            "id": "13",
                            "homeAway": "away",
                            "team": {
                                "id": "13",
                                "abbreviation": "LV",
                                "displayName": "Las Vegas Raiders",
                            },
                            "score": "14",
                        },
                    ],
                    "status": {
                        "clock": 180.0,
                        "displayClock": "3:00",
                        "period": 4,
                        "type": {
                            "state": "in",
                            "completed": False,
                        },
                    },
                    "situation": {
                        "down": 1,
                        "yardLine": 8,  # Inside 20 = red zone
                        "distance": 8,
                        "downDistanceText": "1st & Goal at DEN 8",
                        "possessionText": "LV Ball",
                        "isRedZone": True,
                        "possession": "13",
                    },
                }
            ],
            "status": {
                "period": 4,
                "type": {"state": "in", "completed": False},
            },
        }
    ],
}


# =============================================================================
# Malformed/Edge Case Responses (For Error Handling Tests)
# =============================================================================

ESPN_RESPONSE_MISSING_EVENTS = {
    "leagues": [{"id": "28", "abbreviation": "NFL"}],
    "season": {"type": 2, "year": 2025},
    # Missing "events" key
}

ESPN_RESPONSE_MISSING_COMPETITORS = {
    "leagues": [{"id": "28", "abbreviation": "NFL"}],
    "events": [
        {
            "id": "401547423",
            "name": "Test Game",
            "competitions": [
                {
                    "id": "401547423",
                    # Missing "competitors" key
                    "status": {"type": {"state": "in", "completed": False}},
                }
            ],
        }
    ],
}

ESPN_RESPONSE_NULL_SCORES = {
    "leagues": [{"id": "28", "abbreviation": "NFL"}],
    "events": [
        {
            "id": "401547424",
            "name": "Test Game With Null Scores",
            "competitions": [
                {
                    "id": "401547424",
                    "competitors": [
                        {
                            "id": "1",
                            "homeAway": "home",
                            "team": {"abbreviation": "TM1"},
                            "score": None,  # Null score (pre-game edge case)
                        },
                        {
                            "id": "2",
                            "homeAway": "away",
                            "team": {"abbreviation": "TM2"},
                            "score": None,
                        },
                    ],
                    "status": {"type": {"state": "pre", "completed": False}},
                }
            ],
        }
    ],
}


# =============================================================================
# Rate Limiting Test Data
# =============================================================================

RATE_LIMIT_TEST_SCENARIOS = [
    {
        "name": "normal_request",
        "requests_made": 100,
        "limit_per_hour": 500,
        "should_throttle": False,
    },
    {
        "name": "approaching_limit",
        "requests_made": 480,
        "limit_per_hour": 500,
        "should_throttle": False,
    },
    {
        "name": "at_limit",
        "requests_made": 500,
        "limit_per_hour": 500,
        "should_throttle": True,
    },
    {
        "name": "over_limit",
        "requests_made": 550,
        "limit_per_hour": 500,
        "should_throttle": True,
    },
]
