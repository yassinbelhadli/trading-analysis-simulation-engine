"""Check available coupons."""
import httpx, json

r = httpx.post("http://localhost:8000/auth/login", json={"email": "demo.owner@ict-ea-demo.dev", "password": "OwnerDemo!2026"})
print(f"Login status: {r.status_code}")
print(r.text[:500])
token = r.json()["access_token"]
r = httpx.get("http://localhost:8000/api/admin/coupons", headers={"Authorization": f"Bearer {token}"})
for c in r.json().get("items", []):
    print(json.dumps(c, indent=2, default=str))

# Also check coupon_redemptions
from database.db import async_session_factory
from sqlalchemy import text
import asyncio

async def check():
    async with async_session_factory() as session:
        r = await session.execute(text("SELECT id, coupon_id, user_id, currency FROM coupon_redemptions"))
        for row in r:
            print(f"Redemption: coupon={row[1]} user={row[2]} currency={row[3]}")

asyncio.run(check())
