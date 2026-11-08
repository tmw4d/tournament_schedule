import sqlite3

def init_db():
    conn = sqlite3.connect("tournament.db")
    cursor = conn.cursor()
    
    # Execute the schema DDL statements from database_setup.sql
    with open("database_setup.sql", "r") as schema_file:
        cursor.executescript(schema_file.read())
    
    conn.commit()
    conn.close()