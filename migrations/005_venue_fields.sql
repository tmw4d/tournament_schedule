BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS fields (
    field_id INTEGER PRIMARY KEY AUTOINCREMENT,
    venue_id INTEGER NOT NULL REFERENCES venues(venue_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    UNIQUE (venue_id, name),
    UNIQUE (field_id, venue_id)
);

ALTER TABLE games ADD COLUMN field_id INTEGER REFERENCES fields(field_id);
INSERT INTO fields(venue_id,name)
SELECT v.venue_id,'Field 1' FROM venues v
WHERE NOT EXISTS (SELECT 1 FROM fields f WHERE f.venue_id=v.venue_id);
UPDATE games SET field_id=(SELECT f.field_id FROM fields f WHERE f.venue_id=games.venue_id ORDER BY f.field_id LIMIT 1)
WHERE field_id IS NULL AND venue_id IS NOT NULL;
COMMIT;
