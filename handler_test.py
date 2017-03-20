import ORM
import asyncio
from handlers import api_authenticate, api_register_user


def test_handler(loop):
    yield from ORM.create_pool(loop, user='www-data', password='www-data', db='awesome')
    yield from api_register_user(name='Michael', email='test@orm.org', password='my-pwd')
    yield from api_authenticate(email='test@orm.org', password='my-pwd' )
    ORM.__pool.close()
    yield from ORM.__pool.wait_closed()

loop = asyncio.get_event_loop()
loop.run_until_complete(test_handler(loop))
