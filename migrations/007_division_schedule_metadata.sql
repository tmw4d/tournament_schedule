ALTER TABLE divisions ADD COLUMN description TEXT;
ALTER TABLE divisions ADD COLUMN pool_game_length_minutes INTEGER
    CHECK (pool_game_length_minutes IS NULL OR pool_game_length_minutes > 0);
ALTER TABLE divisions ADD COLUMN playoff_game_length_minutes INTEGER
    CHECK (playoff_game_length_minutes IS NULL OR playoff_game_length_minutes > 0);
