from itertools import izip
from redisengine.exceptions import DoesNotExist, ValidationError
from redisengine.core.tree_base import BaseTreeCore
from redisengine.direct.base.metaclasses import DirectTreeMetaclass

import logging
logger = logging.getLogger(__name__)

__all__ = ("DirectTree", )

class ContextManagersMixin(object):
    def switch_validation(self, state=False):
        def enter(this):
            self._validate = bool(state)
            return self
        def exit(this, *args, **kwargs):
            self._validate = not bool(state)

        return type("ValidationSwitcher", (object,), {
            "__enter__": enter,
            "__exit__": exit
        })()


class DirectTree(BaseTreeCore, ContextManagersMixin):

    _cls_label = "DirectTree"
    # __metaclass__ = DirectTreeMetaclass

    def __init__(self, id, conn=None, validate=False):
        if conn is None:
            raise AttributeError("Can't subclass `DirectTree` manually")
        self._conn = conn
        self._validate = validate
        self._id = str(id)
        self._created = False
        self._active_operators = {}
        if not any(conn.scan_iter(self.pk + "*")):
            raise DoesNotExist("Tree with pk {} not found".format(self.pk))
        self._setValues()

    # @property
    # def id(self):
    #     return self._id

    @BaseTreeCore.id.setter
    def id(self, val):
        raise AttributeError("Can't set `id` on a DirectTree")

    def _setValues(self, values={}):
        # instantiate field's operator
        for field_name, field in self._fields.items():
            if not field_name == "id":
                operator = field.direct_operator
                self._active_operators[field_name] = operator(field, self)

    def _operator_setter(self, field_name, value):
        """A tree-specific extension to field's __set__"""
        try:
            self._active_operators[field_name]._value = value
        except AttributeError:
            operator = self._active_operators[field_name]
            self._active_operators[field_name] = operator._make(value)

    def _operator_deleter(self, field_name, adjusted_value):
        operator = self._active_operators[field_name]
        del operator._value

    def to_redis(self, fields={}, use_db_field=True):
        """
        Return data ready for save with Redis.
        """
        data = {
            "tree": {},
            "complex": {}
        }
        for field, value in fields.iteritems():
            field_name = field.name
            if value is not None and field_name != 'id':
                field_key = field.db_field if use_db_field else field.name
                if field.is_complex:
                    data["complex"][field_key] = value
                else:
                    value = field.to_redis(value, use_db_field=use_db_field)
                    data['tree'][field_key] = value
        return data

    def update(self, **fields):
        field_value_map = {
            self._fields.get(field_name): field_val \
                for field_name, field_val in fields.iteritems()\
                if self._fields.has_key(field_name)}
        if self._validate:
            self.validate(field_value_map.iteritems())
        data = self.to_redis(field_value_map)
        tree_fields = data.pop("tree", {})

        if tree_fields:
            if self._conn.hmset(self.pk, tree_fields):
                logger.debug("Updated {}".format(self.pk))

        for field_name, cleaned_value in data.get("complex", {}).items():
            setattr(self, field_name, cleaned_value)

    def values(self, *keys, **kwargs):
        flat = kwargs.get("flat", False)
        keys = list(keys or self._fields_ordered)
        try:
            keys.remove('id')
            keys.remove('pk')
        except ValueError:
            pass
        # if 'id' in keys:
        #     idx = keys.index('id')
        #     keys[idx] = 'pk'

        fields = [self._db_field_map.get(key, key) for key in keys]

        raw_results = izip(keys, self._conn.hmget(self.pk, fields))
        if flat:
            return [
                val and self._fields.get(field).to_python(val) \
                or getattr(self, field, val) for field, val in raw_results]
        return {
            field: val and self._fields.get(field).to_python(val) \
            or getattr(self, field, val) for field, val in raw_results
        }

    def delete(self):
        self._delete()
