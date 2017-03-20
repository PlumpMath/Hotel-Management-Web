from web import get, post
from ORM import User, TourGroup, Plan, Room, Travel
from aiohttp import web
from api_error import APIError, APIValueError
import hashlib
import time
import uuid
import re
import json


@get('/weixin')
def weixin(signature, timestamp, nonce, echostr):
    token = 'gzc1003'
    temparr = [token, timestamp, nonce]
    temparr.sort()
    newstr = "".join(temparr)
    sha1str = hashlib.sha1(newstr.encode('utf-8'))
    temp = sha1str.hexdigest()
    if signature == temp:
        return echostr


def next_id():
    return '%015d%s000' % (int(time.time()*1000), uuid.uuid4().hex)

COOKIE_NAME = 'awesome_cookie'
COOKIE_KEY = 'gzc'


@get('/')
def home_page():
    plans = yield from Plan.findAll()
    travels = yield from Travel.findAll()
    return {'template': 'home_page.html',
            'plans': plans,
            'travels': travels}


@get('/travels')
def manage_create_travel(request):
    user = request.__user__
    if user is None:
        return web.HTTPFound('/register')
    return {'template': 'travels_edit.html',
            'id': '',
            'action': '/api/travels'}


@post('/api/travels')
def api_create_travel(request, *, name, summary, content):
    user = request.__user__
    if not name:
        pass
    if not summary:
        pass
    if not content:
        pass
    travel = Travel(id=next_id(), user_id=user.id, user_name=user.name,
         name=name, summary=summary, content=content)
    yield from travel.save()
    return travel


def user2cookie(user, max_age):
    expires = str(int(time.time())+max_age)
    s = '%s-%s-%s-%s' % (user.id, user.password, expires, COOKIE_KEY)
    L = [user.id, expires, hashlib.sha1(s.encode('utf-8')).hexdigest()]
    return '-'.join(L)

RE_EMAIL = re.compile('^[a-zA-Z0-9_\-\.]+@[a-zA-Z0-9_\-]+(\.[a-zA-Z0-9]+){1,4}$')
RE_PASSWORD = re.compile('^[a-zA-Z0-9\-\_]{6,40}$')


@get('/register')
def register(request):
    return {'template': 'register.html'}


@get('/signin')
def signin(request):
    return {'template': 'signin.html'}


@post('/api/register')
def api_register_user(*, name, email, password):
    if not name or not name.strip():
        raise APIValueError('name')
    if not email or not RE_EMAIL.match(email):
        raise APIValueError('email')
    if not password or not RE_PASSWORD.match(password):
        raise APIValueError('password')
    if (yield from User.findAll('email=?', [email])):
        raise APIError('Register: failed', 'email', 'Email is already in use.')
    uid = next_id()
    sha1_password = '%s:%s' % (uid, password)
    user = User(id=uid, name=name.strip(), email=email, password=hashlib.sha1(sha1_password.encode('utf-8')).hexdigest())
    yield from user.save()
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.password = '******'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r


@post('/api/authenticate')
def api_authenticate(*, email, password):
    if not email:
        raise APIValueError('email', 'Email can not be empty')
    if not password:
        raise APIValueError('password', 'Password can not be empty')
    user = yield from User.findAll('email=?', [email])
    if len(user) == 0:
        raise APIValueError('email', 'Email does not exist.')
    user = user[0]
    sha1_password = '%s:%s' % (user.id, password)
    sha1 = hashlib.sha1(sha1_password.encode('utf-8')).hexdigest()
    if user.password != sha1:
        raise APIValueError('password', 'Invalid password.')
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    r.content_type='application/json'
    user.password = '******'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r


@get('/choose/plans')
def choose_plans(request):
    user = request.__user__
    if user is None:
        return web.HTTPFound('/register')
    plans = yield from Plan.findAll()
    return {'template': 'choose_plans.html',
            'plans': plans
           }


@post('/api/choose/plans')
def api_choose_plans(*, plan):
    resp = web.HTTPFound('/choose/rooms')
    resp.set_cookie('Plan', plan, max_age=86400, httponly=True)
    return resp


@get('/choose/rooms')
def choose_rooms(request):
    user = request.__user__
    if user is None:
        return web.HTTPFound('/register')
    single_room_remain = yield from Room.findAll('type=? and user is null', ['单人间'])
    double_room_remain = yield from Room.findAll('type=? and user is null', ['双人间'])
    return {'template': 'choose_rooms.html',
            'single_room': len(single_room_remain),
            'double_room': len(double_room_remain)
           }


@post('/api/choose/rooms')
def api_choose_rooms(*, room):
    rooms = yield from Room.findAll('type=? and user is null', [room])
    room_number = rooms[0].number
    resp = web.HTTPFound('/choose/transport')
    resp.set_cookie('Room_type', room, max_age=86400, httponly=True)
    resp.set_cookie('Room_number', room_number, max_age=86400, httponly=True)
    return resp


@get('/choose/transport')
def choose_transport(request):
    user = request.__user__
    if user is None:
        return web.HTTPFound('/register')
    return {'template': 'choose_transport.html'}


@post('/api/choose/transport')
def api_choose_transport(*, transport):
    resp = web.HTTPFound('/confirm')
    resp.set_cookie('Transport', transport, max_age=86400, httponly=True)
    return resp


@get('/confirm')
def confirm(request):
    user = request.__user__
    if user is None:
        return web.HTTPFound('/register')
    plan = request.cookies.get('Plan')
    room_number = request.cookies.get('Room_number')
    room_type = request.cookies.get('Room_type')
    transport = request.cookies.get('Transport')
    user_name = request.__user__.name
    return {'template': 'confirm.html',
            'plan': plan,
            'room_number': room_number,
            'room_type': room_type,
            'transport': transport,
            'user_name': user_name
            }


@post('/api/confirm')
def api_confirm(request):
    plan = request.cookies.get('Plan')
    room_number = request.cookies.get('Room_number')
    transport = request.cookies.get('Transport')
    user_name = request.__user__.name
    user_id = request.__user__.id
    user = TourGroup(id=next_id(), user_id=user_id, user_name=user_name, plan=plan, room=room_number, transport=transport)
    yield from user.save()
    room = yield from Room.find(room_number)
    room.user = user_name
    room.user_id = user_id
    yield from room.update()
    return web.HTTPFound('/')


@get('/manage/plans')
def manage_plans(request):
    return {'template': 'manage_plans.html'}


@post('/api/plans')
def api_create_plans(*, name, content, maximum):
    if not name:
        pass
    if not content:
        pass
    if not max:
        pass
    plan = Plan(name=name, content=content, maximum=maximum)
    yield from plan.save()
    return web.HTTPFound('/manage/plans')


@get('/manage/rooms')
def manage_rooms():
    rooms = yield from Room.findAll()
    return {'template': 'manage_rooms.html',
            'rooms': rooms
           }


@post('/api/rooms/checkout/{number}')
def api_update_room(number):
    room = yield from Room.find(number)
    user = yield from TourGroup.find(room.user_id)
    yield from user.remove()
    room.user = None
    room.user_id = None
    yield from room.update()
    return web.HTTPFound('/manage/rooms')


@get('/api/rooms')
def api_rooms():
    rooms = yield from Room.findAll()
    return {'rooms': rooms}


@get('/api/plans')
def api_plans():
    plans = yield from Plan.findAll()
    return dict(plans=plans)


@get('/api/travels')
def api_travels():
    travels = yield from Travel.findAll()
    return dict(travels=travels)


@get('/api/group')
def api_group():
    group = yield from TourGroup.findAll()
    return dict(group=group)







