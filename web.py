import functools
import asyncio
import os
import inspect
from urllib import parse


def get(path):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = 'GET'
        wrapper.__route__ = path
        return wrapper
    return decorator


def post(path):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kw):
            return func(*args, **kw)
        wrapper.__method__ = 'POST'
        wrapper.__route__ = path
        return wrapper
    return decorator


def has_request_arg(fn):
    sig = inspect.signature(fn)
    params = sig.parameters
    found = False
    for name, param in params.items():
        if name == 'request':
            found = True
    return found


class RequestHandler(object):

    def __init__(self, fn):
        self._func = fn

    @asyncio.coroutine
    def __call__(self, request):
        kw = None
        if request.method == 'POST':
            content_type = request.content_type.lower()
            if content_type.startswith('application/json'):
                params = yield from request.json()
                if isinstance(params, dict):
                    kw = params
            elif content_type.startswith('application/x-www-form-urlencoded') or content_type.startswith('multipart/form-data'):
                params = yield from request.post()
                kw = dict(**params)
        if request.method == 'GET':
            qs = request.query_string
            # http://localhost:8000/api/blogs?page=1
            # ?后的叫query
            # 为了取出query，并将其以dict形式传给handler
            if qs:
                kw = dict()
                for k,v in parse.parse_qs(qs, True).items():
                    kw[k] = v[0]
        if not kw:
            kw = dict(**request.match_info)
        if has_request_arg(self._func):
            kw['request'] = request
        r = yield from self._func(**kw)
        return r


def add_route(app, fn):
    if not asyncio.iscoroutinefunction(fn):
        fn = asyncio.coroutine(fn)
    app.router.add_route(fn.__method__, fn.__route__, RequestHandler(fn))  #RequestHandler的实例相当于URL处理函数名


def add_routes(app, module_name):
    name = __import__(module_name, globals(), locals(), [])
    for attr in dir(name):
        if not attr.startswith('_'):
            fn = getattr(name, attr)
            if callable(fn):
                method = getattr(fn, '__method__', None)
                path = getattr(fn, '__route__', None)
                if method and path:
                    add_route(app, fn)


def add_static(app):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    app.router.add_static('/static/', path)