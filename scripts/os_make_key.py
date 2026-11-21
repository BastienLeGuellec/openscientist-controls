"""Create an OpenScientist API key for the mock admin user (dev mode only).

Run inside the OpenScientist web container, after one visit to /auth/mock/admin-login:
    docker exec -i <web container> python - < os_make_key.py
Prints the key as name:secret. The keys REST endpoint itself needs a key, hence this script.
"""

import asyncio

from sqlalchemy import select

from openscientist.api.auth import generate_api_key_secret, hash_secret
from openscientist.database.models import APIKey, User
from openscientist.database.session import get_admin_session

NAME = "ma-openscientist"


async def main() -> None:
    async with get_admin_session() as db:
        user = (await db.execute(select(User).where(User.email == "admin@mock.local"))).scalar_one()
        old = (await db.execute(select(APIKey).where(APIKey.user_id == user.id, APIKey.name == NAME))).scalars()
        for key in old:
            await db.delete(key)
        await db.flush()      # apply the deletes before the insert (same name is unique per user)
        secret = generate_api_key_secret()
        db.add(APIKey(user_id=user.id, name=NAME, key_hash=hash_secret(secret), is_active=True))
        await db.commit()
    print(f"{NAME}:{secret}")


asyncio.run(main())
