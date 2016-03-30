from functools import partial
from redisengine.direct.tree import DirectTree
from redisengine.exceptions import OperationError

__all__ = ("BaseOperator", )

class BaseOperator(object):
    def __init__(self, field):
        self._lookup_name = field.db_field or field.name
        self._field = field
        self._validate = False
        self._operator_pk = None
        self.pk = None
        self._assigned = False

    def __delete__(self, instance):
        if self._field.required:
            raise OperationError(
                "Can't delete `{}` because it's required".format(self._field.name))
        return self._delObject()

    def __get__(self, instance, owner):
        if instance is not None:
            if not self._assigned:
                self._assignAttrs(instance)
            if self.__class__.__name__ == 'HashOperator':
                return self._getObject()
            return self
        raise AttributeError("Field operator inaccessible for unbound objects")

    def __set__(self, instance, value):
        if isinstance(instance, DirectTree):
            if value is None:
                if self._field.null:
                    value = None
                elif self._field.default is not None:
                    value = self.default
                    if callable(value):
                        value = value()
            if hasattr(self, '_setObject'):
                self._assignAttrs(instance)
                self._field.checkType(value)
                to_redis_value = self.to_redis(value)
                self._setObject(to_redis_value)

    def to_redis(self, value):
        return value

    # def _assignAttrs(self, inst):
    #     self.pk = inst.pk
    #     self._conn = inst._conn
    #     self._validate = inst._validate
    #     self._assigned = True

    @property
    def operator_pk(self):
        return self.pk

    def _delObject(self):
        pass
