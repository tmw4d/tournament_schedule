BEGIN IMMEDIATE;

DROP TABLE IF EXISTS match_sides;
ALTER TABLE matches RENAME TO matches_legacy;

CREATE TABLE matches (
    match_id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_code TEXT NOT NULL,
    division_id INTEGER NOT NULL,
    stage TEXT NOT NULL,
    round_name TEXT,
    pool_id INTEGER,
    venue_id INTEGER,
    scheduled_time DATETIME,
    score_a INTEGER DEFAULT 0,
    score_b INTEGER DEFAULT 0,
    status TEXT DEFAULT 'Scheduled',
    FOREIGN KEY (division_id) REFERENCES divisions(division_id),
    FOREIGN KEY (pool_id, division_id) REFERENCES pools(pool_id, division_id),
    FOREIGN KEY (venue_id) REFERENCES venues(venue_id),
    UNIQUE (division_id, game_code),
    UNIQUE (match_id, division_id)
);

CREATE TABLE match_sides (
    match_id INTEGER NOT NULL,
    division_id INTEGER NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('A', 'B')),
    source_type TEXT NOT NULL CHECK (
        source_type IN ('unresolved', 'team', 'pool_rank', 'match_result')
    ),
    team_id INTEGER,
    pool_id INTEGER,
    pool_rank INTEGER,
    source_match_id INTEGER,
    source_outcome TEXT CHECK (source_outcome IN ('winner', 'loser')),
    PRIMARY KEY (match_id, side),
    CHECK (source_match_id IS NULL OR source_match_id != match_id),
    CHECK (
        (source_type = 'unresolved'
            AND team_id IS NULL AND pool_id IS NULL AND pool_rank IS NULL
            AND source_match_id IS NULL AND source_outcome IS NULL)
        OR (source_type = 'team'
            AND team_id IS NOT NULL AND pool_id IS NULL AND pool_rank IS NULL
            AND source_match_id IS NULL AND source_outcome IS NULL)
        OR (source_type = 'pool_rank'
            AND team_id IS NULL AND pool_id IS NOT NULL
            AND pool_rank IS NOT NULL AND pool_rank > 0
            AND source_match_id IS NULL AND source_outcome IS NULL)
        OR (source_type = 'match_result'
            AND team_id IS NULL AND pool_id IS NULL AND pool_rank IS NULL
            AND source_match_id IS NOT NULL AND source_outcome IS NOT NULL)
    ),
    FOREIGN KEY (match_id, division_id)
        REFERENCES matches(match_id, division_id) ON DELETE CASCADE,
    FOREIGN KEY (team_id) REFERENCES teams(team_id),
    FOREIGN KEY (pool_id, division_id)
        REFERENCES pools(pool_id, division_id),
    FOREIGN KEY (source_match_id, division_id)
        REFERENCES matches(match_id, division_id)
);

INSERT OR IGNORE INTO divisions (name)
SELECT 'Unassigned'
WHERE EXISTS (
    SELECT 1
    FROM matches_legacy AS m
    LEFT JOIN teams AS home_team ON home_team.team_id = m.home_team_id
    LEFT JOIN teams AS away_team ON away_team.team_id = m.away_team_id
    WHERE m.division_id IS NULL
      AND home_team.division_id IS NULL
      AND away_team.division_id IS NULL
);

INSERT INTO matches (
    match_id, game_code, division_id, stage, round_name, pool_id, venue_id,
    scheduled_time, score_a, score_b, status
)
SELECT
    m.match_id,
    'G' || m.match_id,
    COALESCE(m.division_id, home_team.division_id, away_team.division_id,
        (SELECT division_id FROM divisions WHERE name = 'Unassigned')),
    m.stage, m.round_name, NULL, m.venue_id,
    m.scheduled_time, m.home_score, m.away_score, m.status
FROM matches_legacy AS m
LEFT JOIN teams AS home_team ON home_team.team_id = m.home_team_id
LEFT JOIN teams AS away_team ON away_team.team_id = m.away_team_id;

INSERT INTO match_sides (
    match_id, division_id, side, source_type, team_id
)
SELECT
    scheduled.match_id,
    scheduled.division_id,
    'A',
    CASE WHEN t.team_id IS NULL THEN 'unresolved' ELSE 'team' END,
    t.team_id
FROM matches_legacy AS m
JOIN matches AS scheduled ON scheduled.match_id = m.match_id
LEFT JOIN teams AS t
    ON t.team_id = m.home_team_id
UNION ALL
SELECT
    scheduled.match_id,
    scheduled.division_id,
    'B',
    CASE WHEN t.team_id IS NULL THEN 'unresolved' ELSE 'team' END,
    t.team_id
FROM matches_legacy AS m
JOIN matches AS scheduled ON scheduled.match_id = m.match_id
LEFT JOIN teams AS t
    ON t.team_id = m.away_team_id;

DROP TABLE matches_legacy;
CREATE INDEX idx_match_sides_source_match ON match_sides(source_match_id);

COMMIT;
