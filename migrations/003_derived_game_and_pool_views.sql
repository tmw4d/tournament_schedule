BEGIN IMMEDIATE;
DROP VIEW IF EXISTS games_vw;
DROP VIEW IF EXISTS pool_members_vw;
ALTER TABLE matches RENAME TO matches_old;
ALTER TABLE match_sides RENAME TO match_sides_old;
ALTER TABLE pool_teams RENAME TO pool_teams_old;

CREATE TABLE pool_members (
 pool_id INTEGER NOT NULL, team_id INTEGER NOT NULL UNIQUE, division_id INTEGER NOT NULL,
 position TEXT, PRIMARY KEY(pool_id,team_id),
 FOREIGN KEY(pool_id,division_id) REFERENCES pools(pool_id,division_id) ON DELETE CASCADE,
 FOREIGN KEY(team_id,division_id) REFERENCES teams(team_id,division_id) ON DELETE CASCADE
);
INSERT INTO pool_members(pool_id,team_id,division_id)
 SELECT pool_id,team_id,division_id FROM pool_teams_old;

CREATE TABLE games (
 game_id INTEGER PRIMARY KEY AUTOINCREMENT, game_code TEXT NOT NULL, division_id INTEGER NOT NULL,
 stage TEXT NOT NULL, round_name TEXT, pool_id INTEGER, venue_id INTEGER, game_time DATETIME,
 status TEXT NOT NULL DEFAULT 'Scheduled' CHECK(status IN ('Scheduled','In Progress','Final')),
 source_type_a TEXT NOT NULL DEFAULT 'unresolved', source_team_a_id INTEGER,
 source_pool_a_id INTEGER, source_rank_a INTEGER, source_game_a_id INTEGER, source_outcome_a TEXT,
 source_type_b TEXT NOT NULL DEFAULT 'unresolved', source_team_b_id INTEGER,
 source_pool_b_id INTEGER, source_rank_b INTEGER, source_game_b_id INTEGER, source_outcome_b TEXT,
 score_a INTEGER, score_b INTEGER,
 FOREIGN KEY(division_id) REFERENCES divisions(division_id),
 FOREIGN KEY(pool_id,division_id) REFERENCES pools(pool_id,division_id),
 FOREIGN KEY(venue_id) REFERENCES venues(venue_id),
 FOREIGN KEY(source_pool_a_id,division_id) REFERENCES pools(pool_id,division_id),
 FOREIGN KEY(source_pool_b_id,division_id) REFERENCES pools(pool_id,division_id),
 FOREIGN KEY(source_game_a_id,division_id) REFERENCES games(game_id,division_id),
 FOREIGN KEY(source_game_b_id,division_id) REFERENCES games(game_id,division_id),
 UNIQUE(division_id,game_code), UNIQUE(game_id,division_id)
);
INSERT INTO games(game_id,game_code,division_id,stage,round_name,pool_id,venue_id,game_time,status,score_a,score_b,
 source_type_a,source_team_a_id,source_pool_a_id,source_rank_a,source_game_a_id,source_outcome_a,
 source_type_b,source_team_b_id,source_pool_b_id,source_rank_b,source_game_b_id,source_outcome_b)
 SELECT m.match_id,'G'||m.match_id,m.division_id,m.stage,m.round_name,m.pool_id,m.venue_id,m.scheduled_time,m.status,m.score_a,m.score_b,
 COALESCE(CASE a.source_type WHEN 'match_result' THEN 'game_result' ELSE a.source_type END,'unresolved'),a.team_id,a.pool_id,a.pool_rank,a.source_match_id,a.source_outcome,
 COALESCE(CASE b.source_type WHEN 'match_result' THEN 'game_result' ELSE b.source_type END,'unresolved'),b.team_id,b.pool_id,b.pool_rank,b.source_match_id,b.source_outcome
 FROM matches_old m LEFT JOIN match_sides_old a ON a.match_id=m.match_id AND a.side='A'
 LEFT JOIN match_sides_old b ON b.match_id=m.match_id AND b.side='B';
DROP TABLE match_sides_old;
DROP TABLE matches_old;
DROP TABLE pool_teams_old;
COMMIT;
