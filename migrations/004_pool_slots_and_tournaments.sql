BEGIN IMMEDIATE;
DROP VIEW IF EXISTS games_vw;
DROP VIEW IF EXISTS pool_members_vw;

ALTER TABLE divisions ADD COLUMN tournament TEXT NOT NULL DEFAULT 'Tournament';
ALTER TABLE pools ADD COLUMN num_members INTEGER NOT NULL DEFAULT 0 CHECK(num_members >= 0);

ALTER TABLE pool_members RENAME TO pool_members_old;
CREATE TABLE pool_members (
    pool_member_id INTEGER PRIMARY KEY AUTOINCREMENT,
    pool_id INTEGER NOT NULL,
    team_id INTEGER UNIQUE,
    division_id INTEGER NOT NULL,
    position INTEGER NOT NULL CHECK(position > 0),
    UNIQUE(pool_id, position),
    FOREIGN KEY(pool_id, division_id) REFERENCES pools(pool_id, division_id) ON DELETE CASCADE,
    FOREIGN KEY(team_id, division_id) REFERENCES teams(team_id, division_id) ON DELETE CASCADE
);
INSERT INTO pool_members(pool_id,team_id,division_id,position)
SELECT pool_id,team_id,division_id,
       ROW_NUMBER() OVER (PARTITION BY pool_id ORDER BY team_id)
FROM pool_members_old;
DROP TABLE pool_members_old;
UPDATE pools SET num_members=(SELECT COUNT(*) FROM pool_members WHERE pool_members.pool_id=pools.pool_id);
COMMIT;
