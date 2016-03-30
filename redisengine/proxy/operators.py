import weakref
from datetime import datetime

from logging import getLogger
from redisengine.proxy.base.operators import BaseProxyOperator, ComplexProxyOperator

logger = getLogger(__name__)

__all__ = ('ListOperator', 'SetOperator', 'HashOperator')


class HashOperator(BaseProxyOperator):
    pass


class SequenceOperator(ComplexProxyOperator):
    def _create(self, cleaned_value, **k):
        self._write(cleaned_value, "Created", **k)

    def _update(self, cleaned_value):
        self._write(cleaned_value, "Updated")

    def _delete(self):
        return self._conn.delete(self._field_pk)


class ListOperator(SequenceOperator, list):
    def __setitem__(self, *args, **kwargs):
        self._mark_as_changed()
        return super(ListOperator, self).__setitem__(*args, **kwargs)

    def __delitem__(self, key, *args, **kwargs):
        self._mark_as_changed(key)
        return super(ListOperator, self).__delitem__(key)

    def __setslice__(self, *args, **kwargs):
        self._mark_as_changed()
        return super(ListOperator, self).__setslice__(*args, **kwargs)

    def __delslice__(self, *args, **kwargs):
        self._mark_as_changed()
        return super(ListOperator, self).__delslice__(*args, **kwargs)

    def __iadd__(self, other):
        self._mark_as_changed()
        return super(ListOperator, self).__iadd__(other)

    def __imul__(self, other):
        self._mark_as_changed()
        return super(ListOperator, self).__imul__(other)

    def append(self, *args, **kwargs):
        self._mark_as_changed()
        return super(ListOperator, self).append(*args, **kwargs)

    def extend(self, *args, **kwargs):
        self._mark_as_changed()
        return super(ListOperator, self).extend(*args, **kwargs)

    def insert(self, *args, **kwargs):
        self._mark_as_changed()
        return super(ListOperator, self).insert(*args, **kwargs)

    def pop(self, *args, **kwargs):
        self._mark_as_changed()
        return super(ListOperator, self).pop(*args, **kwargs)

    def remove(self, *args, **kwargs):
        self._mark_as_changed()
        return super(ListOperator, self).remove(*args, **kwargs)

    def reverse(self, *args, **kwargs):
        self._mark_as_changed()
        return super(ListOperator, self).reverse()

    def sort(self, *args, **kwargs):
        self._mark_as_changed()
        return super(ListOperator, self).sort(*args, **kwargs)

    def _fetch(self):
        return self._conn.lrange(self._field_pk, 0, -1)

    def _write(self, cleaned_value, op, expireat=None):
        self._conn.delete(self._field_pk)
        if cleaned_value and self._conn.rpush(self._field_pk, *cleaned_value):
            dbg_msg = "{1} LIST at {0._field_pk} for tree {0._inst.pk}.".format(self, op)
            if expireat and self._conn.expireat(self._field_pk, expireat):
                dbg_msg += " It will expire at {}".format(datetime.fromtimestamp(expireat))


class SetOperator(SequenceOperator, set):
    def _fetch(self):
        return self._conn.smembers(self._field_pk)

    def _write(self, cleaned_value, op):
        self._conn.delete(self._field_pk)
        if cleaned_value and self._conn.sadd(self._field_pk, *cleaned_value):
            logger.debug("{1} SET at {0.field_pk} for tree {0._inst.pk}".format(self, op))
