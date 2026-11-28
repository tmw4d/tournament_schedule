PRAGMA foreign_keys = ON;
DROP VIEW IF EXISTS games_vw;
DROP VIEW IF EXISTS pool_members_vw;

CREATE TABLE IF NOT EXISTS divisions (
    division_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    tournament TEXT NOT NULL DEFAULT 'Tournament',
    description TEXT,
    pool_game_length_minutes INTEGER CHECK (pool_game_length_minutes IS NULL OR pool_game_length_minutes > 0),
    playoff_game_length_minutes INTEGER CHECK (playoff_game_length_minutes IS NULL OR playoff_game_length_minutes > 0)
);

CREATE TABLE IF NOT EXISTS venues (
    venue_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    address_or_url TEXT
);

CREATE TABLE IF NOT EXISTS fields (
    field_id INTEGER PRIMARY KEY AUTOINCREMENT,
    venue_id INTEGER NOT NULL REFERENCES venues(venue_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    UNIQUE (venue_id, name),
    UNIQUE (field_id, venue_id)
);

CREATE TABLE IF NOT EXISTS teams (
    team_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    division_id INTEGER NOT NULL REFERENCES divisions(division_id),
    city TEXT,
    state TEXT,
    payment_received_date DATE,
    payment_channel TEXT CHECK (payment_channel IN ('PayPal','Venmo','Zelle','Check')),
    payment_amount NUMERIC CHECK (payment_amount IS NULL OR payment_amount >= 0),
    access_pin TEXT,
    UNIQUE (team_id, division_id)
);

CREATE TABLE IF NOT EXISTS pools (
    pool_id INTEGER PRIMARY KEY AUTOINCREMENT,
    division_id INTEGER NOT NULL REFERENCES divisions(division_id),
    name TEXT NOT NULL,
    num_members INTEGER NOT NULL DEFAULT 0 CHECK (num_members >= 0),
    UNIQUE (division_id, name),
    UNIQUE (pool_id, division_id)
);

CREATE TABLE IF NOT EXISTS pool_members (
    pool_member_id INTEGER PRIMARY KEY AUTOINCREMENT,
    pool_id INTEGER NOT NULL,
    team_id INTEGER UNIQUE,
    division_id INTEGER NOT NULL,
    position INTEGER NOT NULL CHECK (position > 0),
    UNIQUE (pool_id, position),
    FOREIGN KEY (pool_id, division_id) REFERENCES pools(pool_id, division_id) ON DELETE CASCADE,
    FOREIGN KEY (team_id, division_id) REFERENCES teams(team_id, division_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS games (
    game_id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_code TEXT NOT NULL,
    division_id INTEGER NOT NULL REFERENCES divisions(division_id),
    stage TEXT NOT NULL,
    round_name TEXT,
    pool_id INTEGER,
    field_id INTEGER REFERENCES fields(field_id),
    game_time DATETIME,
    status TEXT NOT NULL DEFAULT 'Scheduled' CHECK (status IN ('Scheduled', 'In Progress', 'Final')),
    source_type_a TEXT NOT NULL DEFAULT 'unresolved' CHECK (source_type_a IN ('unresolved','team','pool_rank','pool_position','game_result')),
    source_team_a_id INTEGER,
    source_pool_a_id INTEGER,
    source_rank_a INTEGER,
    source_game_a_id INTEGER,
    source_outcome_a TEXT CHECK (source_outcome_a IN ('winner','loser')),
    source_type_b TEXT NOT NULL DEFAULT 'unresolved' CHECK (source_type_b IN ('unresolved','team','pool_rank','pool_position','game_result')),
    source_team_b_id INTEGER,
    source_pool_b_id INTEGER,
    source_rank_b INTEGER,
    source_game_b_id INTEGER,
    source_outcome_b TEXT CHECK (source_outcome_b IN ('winner','loser')),
    score_a INTEGER,
    score_b INTEGER,
    FOREIGN KEY (pool_id, division_id) REFERENCES pools(pool_id, division_id),
    FOREIGN KEY (source_pool_a_id, division_id) REFERENCES pools(pool_id, division_id),
    FOREIGN KEY (source_pool_b_id, division_id) REFERENCES pools(pool_id, division_id),
    FOREIGN KEY (source_team_a_id) REFERENCES teams(team_id),
    FOREIGN KEY (source_team_b_id) REFERENCES teams(team_id),
    FOREIGN KEY (source_game_a_id, division_id) REFERENCES games(game_id, division_id),
    FOREIGN KEY (source_game_b_id, division_id) REFERENCES games(game_id, division_id),
    UNIQUE (division_id, game_code),
    UNIQUE (game_id, division_id),
    CHECK (source_game_a_id IS NULL OR source_game_a_id != game_id),
    CHECK (source_game_b_id IS NULL OR source_game_b_id != game_id),
    CHECK ((source_type_a='unresolved' AND source_team_a_id IS NULL AND source_pool_a_id IS NULL AND source_rank_a IS NULL AND source_game_a_id IS NULL AND source_outcome_a IS NULL)
        OR (source_type_a='team' AND source_team_a_id IS NOT NULL AND source_pool_a_id IS NULL AND source_rank_a IS NULL AND source_game_a_id IS NULL AND source_outcome_a IS NULL)
        OR (source_type_a='pool_rank' AND source_team_a_id IS NULL AND source_pool_a_id IS NOT NULL AND source_rank_a>0 AND source_game_a_id IS NULL AND source_outcome_a IS NULL)
        OR (source_type_a='pool_position' AND source_team_a_id IS NULL AND source_pool_a_id IS NOT NULL AND source_rank_a>0 AND source_game_a_id IS NULL AND source_outcome_a IS NULL)
        OR (source_type_a='game_result' AND source_team_a_id IS NULL AND source_pool_a_id IS NULL AND source_rank_a IS NULL AND source_game_a_id IS NOT NULL AND source_outcome_a IS NOT NULL)),
    CHECK ((source_type_b='unresolved' AND source_team_b_id IS NULL AND source_pool_b_id IS NULL AND source_rank_b IS NULL AND source_game_b_id IS NULL AND source_outcome_b IS NULL)
        OR (source_type_b='team' AND source_team_b_id IS NOT NULL AND source_pool_b_id IS NULL AND source_rank_b IS NULL AND source_game_b_id IS NULL AND source_outcome_b IS NULL)
        OR (source_type_b='pool_rank' AND source_team_b_id IS NULL AND source_pool_b_id IS NOT NULL AND source_rank_b>0 AND source_game_b_id IS NULL AND source_outcome_b IS NULL)
        OR (source_type_b='pool_position' AND source_team_b_id IS NULL AND source_pool_b_id IS NOT NULL AND source_rank_b>0 AND source_game_b_id IS NULL AND source_outcome_b IS NULL)
        OR (source_type_b='game_result' AND source_team_b_id IS NULL AND source_pool_b_id IS NULL AND source_rank_b IS NULL AND source_game_b_id IS NOT NULL AND source_outcome_b IS NOT NULL))
);

CREATE VIEW IF NOT EXISTS pool_members_vw AS
WITH pool_game_participants AS (
    SELECT g.game_id,
           COALESCE(
             g.pool_id,
             CASE WHEN g.source_pool_a_id=g.source_pool_b_id THEN g.source_pool_a_id END
           ) AS pool_id,
           g.stage, g.status, g.score_a, g.score_b,
           CASE g.source_type_a
             WHEN 'team' THEN g.source_team_a_id
             WHEN 'pool_position' THEN (
               SELECT pm.team_id FROM pool_members pm
               WHERE pm.pool_id=g.source_pool_a_id AND pm.position=g.source_rank_a
             )
           END AS team_a_id,
           CASE g.source_type_b
             WHEN 'team' THEN g.source_team_b_id
             WHEN 'pool_position' THEN (
               SELECT pm.team_id FROM pool_members pm
               WHERE pm.pool_id=g.source_pool_b_id AND pm.position=g.source_rank_b
             )
           END AS team_b_id
    FROM games g
    WHERE g.stage='Pool'
), pool_results AS (
    SELECT pm.pool_id, pm.team_id, pm.position,
           SUM(CASE WHEN g.status='Final' AND g.score_a IS NOT NULL AND g.score_b IS NOT NULL
                     AND ((g.team_a_id=pm.team_id AND g.score_a>g.score_b)
                       OR (g.team_b_id=pm.team_id AND g.score_b>g.score_a))
                    THEN 1 ELSE 0 END) wins,
           SUM(CASE WHEN g.status='Final' AND g.score_a IS NOT NULL AND g.score_b IS NOT NULL
                     AND ((g.team_a_id=pm.team_id AND g.score_a<g.score_b)
                       OR (g.team_b_id=pm.team_id AND g.score_b<g.score_a))
                    THEN 1 ELSE 0 END) losses,
           SUM(CASE WHEN g.status='Final' AND g.score_a IS NOT NULL AND g.score_b IS NOT NULL
                    THEN CASE WHEN g.team_a_id=pm.team_id THEN g.score_a ELSE g.score_b END
                    ELSE 0 END) goals_for,
           SUM(CASE WHEN g.status='Final' AND g.score_a IS NOT NULL AND g.score_b IS NOT NULL
                    THEN CASE WHEN g.team_a_id=pm.team_id THEN g.score_b ELSE g.score_a END
                    ELSE 0 END) goals_against
    FROM pool_members pm
    LEFT JOIN pool_game_participants g ON g.pool_id=pm.pool_id
      AND (g.team_a_id=pm.team_id OR g.team_b_id=pm.team_id)
    GROUP BY pm.pool_id, pm.team_id, pm.position
), ranked AS (
    SELECT pr.*, goals_for-goals_against AS goal_differential,
      ROW_NUMBER() OVER (PARTITION BY pool_id
        ORDER BY wins DESC, losses ASC, (goals_for-goals_against) DESC, position ASC) AS final_rank
    FROM pool_results pr
    WHERE pr.team_id IS NOT NULL
)
SELECT pm.pool_id, pm.position, pm.team_id, t.name AS team_name, pm.division_id,
       COALESCE(r.wins,0) AS wins, COALESCE(r.losses,0) AS losses,
       COALESCE(r.goals_for,0) AS goals_for, COALESCE(r.goals_against,0) AS goals_against,
       COALESCE(r.goal_differential,0) AS goal_differential,
       CASE WHEN pm.team_id IS NOT NULL
              AND EXISTS (SELECT 1 FROM games g WHERE g.pool_id=pm.pool_id AND g.stage='Pool')
              AND NOT EXISTS (
                SELECT 1 FROM games g
                WHERE g.pool_id=pm.pool_id AND g.stage='Pool'
                  AND (g.status!='Final' OR g.score_a IS NULL OR g.score_b IS NULL)
              )
            THEN r.final_rank END AS final_rank
FROM pool_members pm LEFT JOIN teams t ON t.team_id=pm.team_id
LEFT JOIN ranked r ON r.pool_id=pm.pool_id AND r.team_id=pm.team_id;

CREATE VIEW IF NOT EXISTS games_vw AS
WITH RECURSIVE resolved(game_id, side, team_id) AS (
  SELECT game_id, 'A', CASE source_type_a
    WHEN 'team' THEN source_team_a_id
    WHEN 'pool_rank' THEN (SELECT team_id FROM pool_members_vw p WHERE p.pool_id=g.source_pool_a_id AND p.final_rank=g.source_rank_a LIMIT 1)
    WHEN 'pool_position' THEN (SELECT team_id FROM pool_members p WHERE p.pool_id=g.source_pool_a_id AND p.position=g.source_rank_a LIMIT 1)
    END FROM games g WHERE source_type_a IN ('team','pool_rank','pool_position')
  UNION ALL
  SELECT game_id, 'B', CASE source_type_b
    WHEN 'team' THEN source_team_b_id
    WHEN 'pool_rank' THEN (SELECT team_id FROM pool_members_vw p WHERE p.pool_id=g.source_pool_b_id AND p.final_rank=g.source_rank_b LIMIT 1)
    WHEN 'pool_position' THEN (SELECT team_id FROM pool_members p WHERE p.pool_id=g.source_pool_b_id AND p.position=g.source_rank_b LIMIT 1)
    END FROM games g WHERE source_type_b IN ('team','pool_rank','pool_position')
  UNION
  SELECT g.game_id, target.side, participant.team_id
  FROM games g
  JOIN (SELECT 'A' AS side UNION ALL SELECT 'B') target
  JOIN games src ON src.game_id=CASE target.side WHEN 'A' THEN g.source_game_a_id ELSE g.source_game_b_id END
  JOIN resolved participant ON participant.game_id=src.game_id
    AND participant.side=CASE
      WHEN (CASE target.side WHEN 'A' THEN g.source_outcome_a ELSE g.source_outcome_b END)='winner'
        THEN CASE WHEN src.score_a>src.score_b THEN 'A' ELSE 'B' END
      ELSE CASE WHEN src.score_a>src.score_b THEN 'B' ELSE 'A' END END
  WHERE (CASE target.side WHEN 'A' THEN g.source_type_a ELSE g.source_type_b END)='game_result'
    AND src.status='Final' AND src.score_a!=src.score_b
)
SELECT g.*, (SELECT team_id FROM resolved r WHERE r.game_id=g.game_id AND r.side='A' LIMIT 1) AS team_a_id,
       (SELECT team_id FROM resolved r WHERE r.game_id=g.game_id AND r.side='B' LIMIT 1) AS team_b_id,
       CASE WHEN g.status='Final' AND g.score_a>g.score_b THEN (SELECT team_id FROM resolved r WHERE r.game_id=g.game_id AND r.side='A' LIMIT 1)
            WHEN g.status='Final' AND g.score_b>g.score_a THEN (SELECT team_id FROM resolved r WHERE r.game_id=g.game_id AND r.side='B' LIMIT 1) END AS winner_team_id,
       CASE WHEN g.status='Final' AND g.score_a>g.score_b THEN (SELECT team_id FROM resolved r WHERE r.game_id=g.game_id AND r.side='B' LIMIT 1)
            WHEN g.status='Final' AND g.score_b>g.score_a THEN (SELECT team_id FROM resolved r WHERE r.game_id=g.game_id AND r.side='A' LIMIT 1) END AS loser_team_id
FROM games g;
