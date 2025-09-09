from app import init_db, seed_events, app


if __name__ == '__main__':
    with app.app_context():
        init_db()
        seed_events()
        print('Database created and seeded (events.db)')