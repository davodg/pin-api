class UserRepository:
    def __init__(self, db):
        self.db = db

    @staticmethod
    def _user(rows):
        if not rows:
            return None
        return dict(zip(('id', 'username', 'password_hash', 'role', 'is_active'), rows[0]))

    async def get_by_username(self, username):
        return self._user(await self.db.query(
            'SELECT id, username, password_hash, role, is_active FROM app_user WHERE username = %s',
            (username,),
        ))

    async def get_by_id(self, user_id):
        return self._user(await self.db.query(
            'SELECT id, username, password_hash, role, is_active FROM app_user WHERE id = %s',
            (user_id,),
        ))

    async def create(self, user_id, username, password_hash, role):
        await self.db.execute(
            'INSERT INTO app_user (id, username, password_hash, role) VALUES (%s, %s, %s, %s)',
            (user_id, username, password_hash, role),
        )

    async def allow_login(self, address):
        await self.db.execute("DELETE FROM login_attempt WHERE window_start < now() - interval '1 day'")
        rows = await self.db.execute("""
            INSERT INTO login_attempt (address, window_start, attempts)
            VALUES (%s, now(), 1)
            ON CONFLICT (address) DO UPDATE SET
                attempts = CASE WHEN login_attempt.window_start <= now() - interval '60 seconds'
                    THEN 1 ELSE login_attempt.attempts + 1 END,
                window_start = CASE WHEN login_attempt.window_start <= now() - interval '60 seconds'
                    THEN now() ELSE login_attempt.window_start END
            RETURNING attempts <= 10
        """, (address,))
        return rows[0][0]
