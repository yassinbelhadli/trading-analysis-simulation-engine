"""Reset admin password."""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database.db import async_session_factory
from sqlalchemy import select
from database.models import User
from security.auth import hash_password

async def main():
    async with async_session_factory() as s:
        u = (await s.execute(select(User).where(User.email == 'admin@ictfunded.com'))).scalar_one()
        u.password_hash = hash_password('kawtar1998rzn')
        await s.commit()
        print('Admin password updated to: kawtar1998rzn')

asyncio.run(main())
