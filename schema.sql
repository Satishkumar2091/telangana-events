DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS events;
DROP TABLE IF EXISTS requests;


CREATE TABLE users (
id INTEGER PRIMARY KEY AUTOINCREMENT,
username TEXT UNIQUE NOT NULL,
email TEXT,
password_hash TEXT NOT NULL
);


CREATE TABLE events (
id INTEGER PRIMARY KEY AUTOINCREMENT,
title TEXT NOT NULL,
district TEXT,
date_text TEXT,
base_price INTEGER,
description TEXT
);


CREATE TABLE requests (
id INTEGER PRIMARY KEY AUTOINCREMENT,
request_number TEXT UNIQUE NOT NULL,
user_id INTEGER,
event_id INTEGER,
guests INTEGER,
services TEXT,
total_price INTEGER,
created_at TEXT,
status TEXT,
contact_name TEXT,
contact_phone TEXT,
additional_info TEXT,
FOREIGN KEY(user_id) REFERENCES users(id),
FOREIGN KEY(event_id) REFERENCES events(id)
);