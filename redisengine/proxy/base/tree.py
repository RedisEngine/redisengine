import json
import time
from datetime import datetime
from logging import getLogger

from collections import defaultdict
from redisengine.core.tree_base import BaseTreeCore
from redisengine.connection import get_connection
from redisengine.exceptions import ValidationError, OperationError

logger = getLogger(__name__)

class BaseProxyTree(BaseTreeCore):
    __slots__ = ('_changed_fields', '_deleted_fields', '_initialised', '_created', '_active_operators',
                 '_db_field_map')

    _cls_label = "ProxyTree"

    def __init__(self, **values):
        """
        Initialise a tree.
        :param values: A dictionary of values for the tree
        """
        self._initialised = False
        self._created = True
        self._conn = get_connection(self._meta.db_alias)
        self._active_operators = {}
        self._only_fields = []
        self._id = None

        if "pk" in values:
            self.id = values.pop('pk')

        self._setValues(values)

        # Flag initialised
        self._initialised = True

    # def __unicode__(self):
    #     return u'{0.__class__.__name__} ProxyTree object'.format(self)

    @classmethod
    def _instantiate(cls, data={}, **kwargs):
        only = kwargs.get("only", [])
        inst = cls(**data)
        inst._created = False
        inst._only_fields = only

        if not only:
            complex_fields = inst._complex_fields.items()
        else:
            complex_fields = ((f_name, f) \
                    for f_name, f in inst._complex_fields.items() \
                    if f_name in only)

        for field_name, field in complex_fields:
            operator = inst._active_operators[field_name]
            value = field.to_python(operator._fetch())
            setattr(inst, field_name, value)

        inst._clear_changed_fields()
        return inst

    def _operator_setter(self, field_name, value):
        """A tree-specific extension to field's __set__"""
        if self._only_fields and field_name not in self._only_fields:
            return

        operator = self._active_operators[field_name]
        try:
            operator_value = operator._value
        except AttributeError:
            operator_value = operator

        # check if value changed
        if self._initialised:
            try:
                if (operator_value != value):
                        self._mark_as_changed(field_name)
            except Exception:
                # Values cant be compared eg: naive and tz datetimes
                # So mark it as changed
                self._mark_as_changed(field_name)
            finally:
                # clear the field name from pending deletion list
                try:
                    self._deleted_fields.remove(field_name)
                except (ValueError, AttributeError):
                    pass
        try:
            operator._value = value
        except AttributeError:
            self._active_operators[field_name] = operator._make(value)

    def _operator_deleter(self, field_name, adjusted_value):
        if self._initialised:
            operator = self._active_operators[field_name]
            try:
                operator._value = adjusted_value
            except AttributeError:
                self._active_operators[field_name] = operator._make(adjusted_value)
            self._mark_as_deleted(field_name)


    def _setValues(self, values={}):
        # instantiate field's operator
        for field_name, field in self._fields.items():
            self._active_operators[field_name] = field.proxy_operator(field, self)
            # update `values` with defaults, if necessary
            if field_name not in values or values[field_name] is None:
                if field.null:
                    val = None
                elif field.default is not None:
                    val = field.default
                    if callable(field.default):
                        val = field.default()
                else:
                    continue
                values[field_name] = val

        # Set passed values after initialisation
        for key, value in values.iteritems():
            key = self._reverse_db_field_map.get(key, key)
            if key in self._fields:
                if value is not None:
                    field = self._fields.get(key)
                    if field:
                        value = field.to_python(value)
                setattr(self, key, value)

        # Set any get_fieldname_display methods
        self.__set_field_display()

    def reload(self, *fields):
        if self._created:
            return
        self._acquire_pk()
        fields = fields or self._fields.keys()
        self._only_fields = []
        for field_name in fields:
            if field_name not in self._fields or field_name == "id":
                continue
            field = self._fields[field_name]
            if not field.is_complex:
                lookup_name = self._db_field_map[field_name]
                value = self._conn.hget(self.pk, lookup_name)
            else:
                operator = self._active_operators[field_name]
                value = operator._fetch()
            if value:
                setattr(self, field_name, field.to_python(value))

    def to_redis(self, use_db_field=True, fields=[]):
        """
        Return data ready for use with Redis.
        Call only after _acquire_pk has been invoked.
        """
        data = {
            "tree": {},
            "complex": {}
        }
        # TODO: DIFFERENTIATE behavior for update and save
        for field_name in (fields or self):
            value = getattr(self, field_name, None)
            field = self._fields.get(field_name)

            if value is not None and field_name != 'id':
                value = field.to_redis(value, use_db_field=use_db_field)
                field_key = field.db_field if use_db_field else field.name

                if field.is_complex:
                    data["complex"][field.name] = value
                else:
                    data['tree'][field_key] = value

        return data

    def _acquire_pk(self):
        if self.id is None:
            if self._meta.has_auto_pk:
                # increment index before commiting
                pk_index = self._conn.incr(self._meta.tree_index_key)
                self.id = str(pk_index)
                return self.pk
            else:
                try:
                    return self.pk
                except AttributeError:
                    raise ValidationError("User-specified pk field cannot be None")
        return self.pk

    def perform_create(self, ttl, forced=False):
        """
        :param forced: If True, will commit to db without checking if the pk is there already

        """
        now = int(time.time())
        expireat = None
        tree_pk = self._acquire_pk()
        data = self.to_redis()
        tree_fields = data.pop("tree", {})
        complex_data = data.get("complex", {})

        if not forced and self._conn.exists(tree_pk):
            raise ValidationError(
                "Primary key `{}` already exists. "
                "To override, call ``save`` with forced=True".format(tree_pk))

        if tree_fields and self._conn.hmset(tree_pk, tree_fields):
            dbg_msg = "Created {}.".format(tree_pk)
            if ttl:
                expireat = now + ttl
                if self._conn.expireat(tree_pk, expireat):
                    dbg_msg += " Will expire at {}".format(datetime.fromtimestamp(expireat))
            logger.debug(dbg_msg)

        for field_name, cleaned_value in complex_data.items():
                self._active_operators[field_name]._create(
                        cleaned_value,
                        expireat=expireat)
        self._created = False
        return self._id

    def perform_update(self):
        """If the same field is chosen to be both deleted and updated, it will be deleted"""
        tree_pk = self._acquire_pk()
        deleted_fields = self._get_deleted_fields()
        data = self.to_redis(fields=self._changed_fields)
        tree_fields = data.pop("tree", {})

        if tree_fields:
            if self._conn.hmset(tree_pk, tree_fields):
                logger.debug("Updated {}".format(tree_pk))

        for field_name, cleaned_value in data.get("complex", {}).items():
            self._active_operators[field_name]._update(cleaned_value)

        if self._deleted_fields:
            tree_fields = deleted_fields.get("tree", [])
            complex_fields = deleted_fields.get("complex", {})
            dbg_msg = ""
            if self._conn.hdel(self.pk, *tree_fields):
                dbg_msg += "Deleted tree field(s): {}".format(tree_fields)

            deleted_complex_fields = [operator._delete() and operator._field_name \
                                      for operator in complex_fields]
            if deleted_complex_fields:
                dbg_msg += ", together with the following associated fields: {}".format(deleted_complex_fields)
            logger.debug(dbg_msg)
        return self._id

    def to_json(self, *args, **kwargs):
        """Converts a document to JSON.
            :param use_db_field: Set to True by default but enables the output
                of the json structure with the field names and not the mongodb
                store db_names in case of set to False
        """
        use_db_field = kwargs.pop('use_db_field', True)
        return json.dumps(self.to_redis(use_db_field), *args, **kwargs)

    @classmethod
    def from_json(cls, json_data, created=False):
        """Converts json data to an unsaved document instance"""
        return json.loads(json_data)

    def _mark_as_changed(self, key):
        """Marks a key as explicitly changed by the user"""
        if not key or not hasattr(self, '_changed_fields'):
            return
        key = self._db_field_map.get(key, key)
        if key not in self._changed_fields:
            self._changed_fields.append(key)

    def _mark_as_deleted(self, key):
        """Marks a key as deleted"""
        if not key or not hasattr(self, '_deleted_fields'):
            return
        if key not in self._deleted_fields:
            self._deleted_fields.append(key)
            try:
                self._changed_fields.remove(self.name)
            except ValueError:
                pass

    def _clear_changed_fields(self):
        """Using get_changed_fields iterate and remove any fields that are
        marked as changed"""
        self._changed_fields = []
        self._deleted_fields = []

    def _get_deleted_fields(self):
        deleted_field_names = getattr(self, '_deleted_fields', [])
        deleted_fields = {
            "tree": [],
            "complex": []
        }
        for field_name in deleted_field_names:
            lookup_name = self._db_field_map[field_name]
            if field_name in self._hash_field_names:
                deleted_fields['tree'].append(lookup_name)
            else:
                operator = self._active_operators[field_name]
                deleted_fields['complex'].append(operator)
        return deleted_fields

    def __set_field_display(self):
        """Dynamically set the display value for a field with choices"""
        for attr_name, field in self._fields.items():
            if field.choices:
                obj = type(self)
                setattr(obj,
                        'get_%s_display' % attr_name,
                        partial(self.__get_field_display, field=field))

    def __get_field_display(self, field):
        """Returns the display value for a choice field"""
        value = getattr(self, field.name)
        if field.choices and isinstance(field.choices[0], (list, tuple)):
            return dict(field.choices).get(value, value)
        return value
