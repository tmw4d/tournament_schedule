-- 1. Divisions Table (e.g., Division A, B, C)
CREATE TABLE IF NOT EXISTS divisions (
    division_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

-- 2. Venues / Locations Table (Fields or courts across multiple sites)
CREATE TABLE IF NOT EXISTS venues (
    venue_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    address_or_url TEXT
);

-- 3. Teams Table (~50 teams distributed across divisions)
CREATE TABLE IF NOT EXISTS teams (
    team_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    division_id INTEGER,
    pool_identifier TEXT, -- e.g., 'Pool 1', 'Pool 2'
    access_pin TEXT,      -- 4-digit PIN for authorized score submission
    FOREIGN KEY (division_id) REFERENCES divisions(division_id)
);

-- 4. Matches Table (Handles both Pool Play and Playoff stages)
CREATE TABLE IF NOT EXISTS matches (
    match_id INTEGER PRIMARY KEY AUTOINCREMENT,
    division_id INTEGER,
    stage TEXT NOT NULL,          -- 'Pool' or 'Playoff'
    round_name TEXT,              -- e.g., 'Pool Play', 'Semifinal', 'Final'
    home_team_id INTEGER,
    away_team_id INTEGER,
    venue_id INTEGER,
    scheduled_time DATETIME,
    home_score INTEGER DEFAULT 0,
    away_score INTEGER DEFAULT 0,
    status TEXT DEFAULT 'Scheduled', -- 'Scheduled', 'In Progress', 'Final'
    FOREIGN KEY (division_id) REFERENCES divisions(division_id),
    FOREIGN KEY (home_team_id) REFERENCES teams(team_id),
    FOREIGN KEY (away_team_id) REFERENCES teams(team_id),
    FOREIGN KEY (venue_id) REFERENCES venues(venue_id)
);