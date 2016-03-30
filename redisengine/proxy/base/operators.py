import weakref

class BaseProxyOperator(object):
    def __init__(self, field, inst):
        self._field = field
        self._lookup_name = field.db_field or field.name
        self._value = None
        self._conn = inst._conn
        try:
            self._inst = weakref.proxy(inst)
        except TypeError:
            self._inst = inst

    @property
    def _field_pk(self):
        pk = self._inst.pk
        return ":".join((pk, self._lookup_name))


class ComplexProxyOperator(object):
    def __init__(self, field, inst, *args, **kwargs):
        self._field = field
        self._field_name = field.name
        self._lookup_name = field.db_field or field.name
        self._conn = inst._conn
        try:
            self._inst = weakref.proxy(inst)
        except TypeError:
            self._inst = inst
        super(ComplexProxyOperator, self).__init__(*args, **kwargs)

    @property
    def _field_pk(self):
        pk = self._inst.pk
        return ":".join((pk, self._lookup_name))

    def __setattr__(self, name, value):
        if name == "_value":
            raise AttributeError("`_key` cannot be set explicitly on ComplexProxyOperator")
        super(ComplexProxyOperator, self).__setattr__(name, value)

    def _mark_as_changed(self, key=None):
        if hasattr(self._inst, '_mark_as_changed'):
            self._inst._mark_as_changed(self._field_name)

    def _make(self, value):
        return self.__class__(self._field, self._inst, value)
