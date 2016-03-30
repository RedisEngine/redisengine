import weakref
from redisengine.direct.base.operators import BaseOperator
from redisengine.utils import cached_property

__all__ = ('HashOperator', 'ListOperator', 'IntegerOperator')

class BaseOperator(object):
    def __init__(self, field, inst):
        self._field = field
        self._lookup_name = field.db_field or field.name
        self._conn = inst._conn
        self._pk = inst.pk
        self._inst = weakref.proxy(inst)

        try:
            self._inst = weakref.proxy(inst)
        except TypeError:
            self._inst = inst

    def _make(self, value):
        return self.__class__(self._field, self._inst)

    @property
    def _validate(self):
        return self._inst._validate

class HashOperator(BaseOperator):
    @property
    def _operator_pk(self):
        return self._inst.pk

    def _getObject(self):
        value = self._conn.hget(self._operator_pk,
                                self._lookup_name) or self._field.default
        cleaned_value = self._field.to_python(value)
        return cleaned_value

    def _setObject(self, value):
        return self._conn.hset(self._operator_pk,
                               self._lookup_name, value)

    def to_redis(self, value):
        if self._validate:
            self._field.validate(value)
        return self._field.to_redis(value)

    def _delObject(self):
        self._conn.hdel(self._operator_pk, self._lookup_name)

    @property
    def _value(self):
        return self._getObject()

    @_value.setter
    def _value(self, val):
        value = self.to_redis(val)
        self._setObject(value)

    @_value.deleter
    def _value(self):
        self._delObject()


class IntegerOperator(HashOperator):
    def __add__(self, other):
        try:
            if self._validate:
                self._field.validate(other)
            value = self._field.to_redis(other)
            self._conn.hincrby(self._operator_pk, self._lookup_name, value)
        except Exception, e:
            print e
            return self._getObject() + other

    def __sub__(self, other):
        try:
            if self._validate:
                self._field.validate(other)
            value = -self._field.to_redis(other)
            self._conn.hincrby(self._operator_pk, self._lookup_name, value)
        except:
            return self._getObject() - other

    def __int__(self):
        return self._getObject()

    def __repr__(self):
        return str(self._getObject())


class FloatOperator(IntegerOperator):
    def __add__(self, other):
        try:
            if self._validate:
                self._field.validate(other)
            value = self._field.to_redis(other)
            self._conn.hincrbyfloat(self._operator_pk, self._lookup_name, value)
        except Exception, e:
            print e
            return self._getObject() + other

    def __sub__(self, other):
        try:
            if self._validate:
                self._field.validate(other)
            value = -self._field.to_redis(other)
            self._conn.hincrbyfloat(self._operator_pk, self._lookup_name, value)
        except:
            return self._getObject() - other


class IntegerOperator(HashOperator):
    pass

class FloatOperator(HashOperator):
    pass

class SequenceOperator(BaseOperator):
    @cached_property
    def _operator_pk(self):
        return ":".join((self._pk, self._lookup_name))

    def _getObject(self):
        pass

    def _delete(self):
        self._conn.delete(self._operator_pk)

    def _setObject(self, value):
        self._conn.delete(self._operator_pk)
        self._conn.rpush(self._operator_pk, *value)

    def to_redis(self, value):
        if self._validate:
            self._field.validate(value)
        return self._field.to_redis(value)

    @property
    def _value(self):
        raise AttributeError()

    @_value.setter
    def _value(self, val):
        # because val could be []
        if not val:
            return self._delete()
        value = self.to_redis(val)
        self._setObject(value)

    @_value.deleter
    def _value(self):
        self._delete()


class ListOperator(SequenceOperator):
    OBJ_LEN_LIMIT = 10
    __list_len = property(lambda self: self._conn.llen(self._operator_pk))

    def lappend(self, val):
        value = self.to_redis([val])
    	return self._conn.lpush(self._operator_pk, value[0])

    def rappend(self, val):
        value = self.to_redis([val])
    	return self._conn.rpush(self._operator_pk, value[0])

    def lextend(self, *vals):
    	# encoded_vals = [val for val in vals]
    	return self._conn.lpush(self._operator_pk, *vals)

    def rextend(self, *vals):
    	# encoded_vals = [val) for val in vals]
    	return self._conn.rpush(self._operator_pk, *vals)

    def lpop(self):
    	return self._conn.lpop(self._operator_pk)

    def rpop(self):
    	return self._conn.rpop(self._operator_pk)

    def trim(self, start, end):
    	"Remove ALL values NOT within the slice between ``start`` and ``end``."
    	return self._conn.ltrim(self._operator_pk, start, end)

    def __add__(self, new_item):
        value = self.to_redis(new_item)
    	return self.rappend(value)

    def __eq__(self, other):
        value = self._conn.lrange(self._operator_pk, 0, -1)
        return self._field.to_python(value) == other

    def __getitem__(self, index):
    	value = self._conn.lindex(self._operator_pk, index)
        return self._field.to_python([value])[0]

    def __delitem__(self, index):
    	"Get list's element by ``index`` and replace it with ``None``."
    	self[index] = None

    def __setitem__(self, index, item):
        item = self.to_redis([item])
    	return self._conn.lset(self._operator_pk, index, item[0])

    def __getslice__(self, start, end):
        return self._field.to_python(
                self._conn.lrange(self._operator_pk, start, end))

    def __iter__(self):
    	for el in self._conn.lrange(self._operator_pk, 0, -1):
    		yield self._field.to_python([el])[0]

    def __len__(self):
    	return self.__list_len

    def __repr__(self):
    	obj_length = self.__list_len
    	frmt = u"<{} [{}{}]>"
    	if obj_length > self.OBJ_LEN_LIMIT:
            value = self._conn.lrange(self._operator_pk, 0, self.OBJ_LEN_LIMIT)
            retval = frmt.format(self.__class__.__name__,
        			u", ".join(self._field.to_python(value)),
        			", (... and {} more)".format(obj_length - self.OBJ_LEN_LIMIT))
    	else:
            value = self._conn.lrange(self._operator_pk, 0, -1)
            retval =  frmt.format(self.__class__.__name__,
    			     u", ".join(self._field.to_python(value)), '')
    	return retval
