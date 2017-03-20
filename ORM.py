import asyncio
import aiomysql
import time
import uuid


@asyncio.coroutine
def create_pool(loop, **kw):
    global __pool
    __pool = yield from aiomysql.create_pool(
        host=kw.get('host', 'localhost'),
        port=kw.get('port', 3306),
        user=kw['user'],
        password=kw['password'],
        db=kw['db'],
        charset=kw.get('charset', 'utf8'),
        autocommit=kw.get('autocommit', True),
        maxsize=kw.get('maxsize', 10),
        minsize=kw.get('minsize', 1),
        loop=loop
    )


@asyncio.coroutine
def select(sql, args, size=None):
    with (yield from __pool) as conn:
        cur = yield from conn.cursor(aiomysql.DictCursor)
        yield from cur.execute(sql.replace('?', '%s'), args)
        if size:
            rs = yield from cur.fetchmany(size)
        else:
            rs = yield from cur.fetchall()
        yield from cur.close()
    return rs


@asyncio.coroutine
def execute(sql, args):
    with (yield from __pool) as conn:
        cur = yield from conn.cursor()
        yield from cur.execute(sql.replace('?', '%s'), args)
        affected = cur.rowcount
        yield from cur.close()
    return affected


def create_args_string(num):
    L = []
    for i in range(num):
        L.append('?')
    return ','.join(L)


class Field(object):

    def __init__(self, name, colume_type, primary_key, default):
        self.name = name
        self.colume_type = colume_type
        self.primary_key = primary_key
        self.default = default

    def __str__(self):
        return '<%s:%s>' % (self.__class__.__name__, self.name)


class StringField(Field):
    def __init__(self, name=None, colume_type='varchar(50)', primary_key=False, default=None):
        super().__init__(name, colume_type, primary_key, default)


class TextField(Field):
    def __init__(self, name=None, colume_type='mediumtext', primary_key=False, default=None):
        super().__init__(name, colume_type, primary_key, default)


class BooleanField(Field):
    def __init__(self, name=None, default=False):
        super().__init__(name, 'boolean', False, default)

# class IntegerField(Field):
#     def __init__(self, name):
#         super().__init__(name, 'bigint')


class ModelMetaclass(type):
    def __new__(cls, name, bases, attrs):
        if name == 'Model':
            return type.__new__(cls, name, bases, attrs)
        tablename = attrs.get('__table__', None) or name
        # print('Found model: %s (table: %s)' % (name, tablename))
        mappings = dict()
        fields = []
        primaryKey = None

        for k, v in attrs.items():
            if isinstance(v, Field):
                # print('Found mapping: %s ==>%s' % (k, v))
                mappings[k] = v
                if v.primary_key:
                    if primaryKey:
                        raise RuntimeError('Duplicate primary key for '
                                           'field: %s' % k)
                    primaryKey = k
                else:
                    fields.append(k)
        for k in mappings.keys():
            attrs.pop(k)  # 删除User类中的id name等属性后，因实例
            # self没有 id name 等属性，args.append(getattr(self,k,None)）
            # 会通过__getattr__取得实例属性self[k]，即id name等的实际值；
            # 若不删除，执行args.append(getattr(self,k,None)）时，
            # 会通过self.k获得User类中定义的属性，即id name等对应数据库中表的列
        escaped_fields = list(map(lambda f: '`%s`' % f, fields))
        attrs['__mapping__'] = mappings
        attrs['__table__'] = tablename
        attrs['__primary_key__'] = primaryKey
        attrs['__fields__'] = fields
        attrs['__select__'] = 'select `%s`, %s from `%s`' % \
                              (primaryKey, ','.join(escaped_fields), tablename)
        attrs['__insert__'] = 'insert into `%s` (%s, `%s`) values (%s)' % \
                              (tablename, ','.join(escaped_fields), primaryKey, create_args_string(len(fields) + 1))
        attrs['__update__'] = 'update `%s` set %s where `%s`=?' % \
                              (tablename, ', '.join(map(lambda f: '`%s`=?' % f, fields)), primaryKey)
        attrs['__delete__'] = 'delete from `%s` where `%s`=?' % (tablename, primaryKey)
        return type.__new__(cls, name, bases, attrs)


class Model(dict, metaclass=ModelMetaclass):
    # def __init__(self, **kw):
    #     super().__init__(**kw)

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(r"'Model' object has no attribute '%s'" % key)

    def __setattr__(self, key, value):
        self[key] = value

    def getValue(self, key):
        return getattr(self, key, None)

    def getValueOrDefault(self, key):
        value = getattr(self, key, None)
        if value is None:
            field = self.__mapping__[key]
            if field.default is not None:
                value = field.default() if callable(field.default) else field.default
                setattr(self, key, value)
        return value

    @classmethod
    @asyncio.coroutine
    def find(cls, pk):
        rs = yield from select('%s where `%s`=?'
        % (cls.__select__, cls.__primary_key__), [pk], 1)
        if len(rs) == 0:
            return None
        return cls(**rs[0])

    @classmethod
    @asyncio.coroutine
    def findAll(cls, where=None, args=None):
        sql = [cls.__select__]
        if where:
            sql.append('where')
            sql.append(where)
        rs = yield from select(' '.join(sql), args)
        return [cls(**r) for r in rs]

    @asyncio.coroutine
    def save(self):
        args = list(map(self.getValueOrDefault, self.__fields__))
        args.append(self.getValueOrDefault(self.__primary_key__))
        #args = tuple(args)
        row = yield from execute(self.__insert__, args)

    @asyncio.coroutine
    def update(self):
        args = list(map(self.getValue, self.__fields__))
        args.append(self.getValue(self.__primary_key__))
        row = yield from execute(self.__update__, args)

    @asyncio.coroutine
    def remove(self):
        args = [self.getValue(self.__primary_key__)]
        rows = yield from execute(self.__delete__, args)


def next_id():
    return '%015d%s000' % (int(time.time()*1000), uuid.uuid4().hex)


class User(Model):
    __table__ = 'users'
    id = StringField(primary_key=True, default=next_id)
    name = StringField()
    email = StringField()
    password = StringField()
    admin = BooleanField()


class TourGroup(Model):
    __table__ = 'tour_group'
    user_id = StringField(primary_key=True)
    user_name = StringField()
    plan = StringField()
    room = StringField()
    transport = StringField()


class Plan(Model):
    __table__ = 'plans'
    id = StringField(primary_key=True, default=next_id)
    name = StringField()
    content = TextField()
    maximum = StringField(colume_type='varchar(10)')


class Travel(Model):
    __table__ = 'travels'
    id = StringField(primary_key=True, default=next_id)
    user_id = StringField()
    user_name = StringField()
    name = StringField()
    summary=StringField(colume_type='text')
    content = TextField()


class Room(Model):
    __table__ = 'rooms'
    number = StringField(primary_key=True)
    type = StringField()
    user_id = StringField()
    user = StringField()

@asyncio.coroutine
def test(loop):
    yield from create_pool(loop, user='www-data',  password='www-data', db='awesome')
    # u = User(name='Test', email='test@example.com', password='1234567890')
    # yield from u.save()
    # u = yield from User.findAll('email=?', ['test@example.com'])
    u = yield from Room.findAll()
    print(u)
    __pool.close()
    yield from __pool.wait_closed()

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(test(loop))
    loop.close()