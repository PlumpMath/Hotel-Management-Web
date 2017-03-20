import asyncio
import json
import time
import hashlib
import ORM
from aiohttp import web
from jinja2 import Environment, FileSystemLoader
from web import add_routes, add_static
from ORM import User


COOKIE_NAME = 'awesome_cookie'
COOKIE_KEY = 'gzc'


@asyncio.coroutine
def cookie2user(cookie):
    L = cookie.split('-')
    if len(L) != 3:
        return None
    uid, expires, sha1 = L
    if int(expires) < time.time():
        return None
    user = yield from User.find(uid)
    if not user:
        return None
    s = '%s-%s-%s-%s' % (user.id, user.password, expires, COOKIE_KEY)
    if sha1 != hashlib.sha1(s.encode('utf-8')).hexdigest():
        return None
    user.password = '******'
    return user


@asyncio.coroutine
def response_factory(app, handler):
    @asyncio.coroutine
    def response_handler(request):
        resp = yield from handler(request)
        if isinstance(resp, web.StreamResponse):
            return resp
        if isinstance(resp, str):
            resp = web.Response(body=resp.encode('utf-8'))
            resp.content_type = 'text/html;charset=utf-8'
            return resp
        if isinstance(resp, dict):
            if resp.get('template'):
                template = env.get_template(resp['template'])
                body = template.render(resp)
                resp = web.Response(body=body.encode('utf-8'))
                resp.content_type = 'text/html;charset=utf-8'
                return resp
            else:
                body = json.dumps(resp, ensure_ascii=False)
                resp = web.Response(body=body.encode('utf-8'))
                resp.content_type = 'text/html;charset=utf-8'
                return resp
    return response_handler


@asyncio.coroutine
def auth_factory(app, handler):
    @asyncio.coroutine
    def auth_handler(request):
        request.__user__ = None
        cookie = request.cookies.get(COOKIE_NAME)
        if cookie:
            user = yield from cookie2user(cookie)
            if user:
                request.__user__ = user
        return (yield from handler(request))
    return auth_handler


@asyncio.coroutine
def init(loop): #init()为generator，只要函数中有yield、yield from，则为generator
    yield from ORM.create_pool(loop, user='www-data', password='www-data', db='awesome')
    app = web.Application(loop=loop, middlewares=[response_factory, auth_factory])
    add_routes(app, 'handlers')
    add_static(app)
    srv = yield from loop.create_server(app.make_handler(), '127.0.0.1', 8000)   #loop.create_server()为generator
    print('Server started at http://127.0.0.1:8000...')
    return srv


env = Environment(loader=FileSystemLoader('C:/Users/gzc/PycharmProjects/www/templates'))
loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()