import sqlite3

connection = sqlite3.connect("instance/anter.db")
rows = connection.execute(
    "SELECT id, username, name, is_verified FROM users ORDER BY id"
).fetchall()
for row in rows:
    print(row)
connection.close()
