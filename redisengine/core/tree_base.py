import logging

from redisengine.connection import get_connection
from redisengine.utils import cached_property
from redisengine.exceptions import ValidationError

NON_FIELD_ERRORS = '__all__'
logger = logging.getLogger(__name__)

class BaseTreeCore(object):

    _cls_label = ""

    def __iter__(self):
        return iter(self._fields_ordered)

    def __getitem__(self, name):
        """Dictionary-style field access, return a field's value if present.
        """
        try:
            if name in self._fields_ordered:
                return getattr(self, name)
        except AttributeError:
            pass
        raise KeyError(name)

    def __setitem__(self, name, value):
        """Dictionary-style field access, set a field's value.
        """
        # Ensure that the field exists before settings its value
        if name not in self._fields:
            raise KeyError(name)
        return setattr(self, name, value)

    def __contains__(self, name):
        try:
            val = getattr(self, name)
            return val is not None
        except AttributeError:
            return False

    def __len__(self):
        return len(self._active_operators)

    def __eq__(self, other):
        if isinstance(other, self.__class__) and hasattr(other, 'id') and other.id is not None:
            return self.id == other.id
        if self.id is None:
            return self is other
        return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        if getattr(self, pk, None) is None:
            # For new object
            return super(BaseTreeCore, self).__hash__()
        else:
            return hash(getattr(self, pk))

    def __repr__(self):
        try:
            u = self.__str__()
        except (UnicodeEncodeError, UnicodeDecodeError):
            u = '[Bad Unicode data]'
        repr_type = str if u is None else type(u)
        return repr_type('<%s %s: %s>' % (self.__class__.__name__, self._cls_label, u))

    def __str__(self):
        if hasattr(self, '__unicode__'):
            return unicode(self).encode('utf-8')
        return u'%s object' % self.__class__.__name__

    @property
    def id(self):
        return self._id

    @id.setter
    def id(self, val):
        self._id = str(val)

    @property
    def pk(self):
        if self.id is None:
            raise AttributeError("pk unavailable as id not yet assigned")
        return ":".join((self._meta.tree_key_prefix, self.id))

    @pk.setter
    def pk(self, val):
        if self._meta.has_auto_pk:
            raise AttributeError("Can't set a new pk value if AutoPrimaryKey used")
        self.id = val

    @cached_property
    def _complex_field_names(self):
        return [field_name for field_name, field in self._fields.items() \
                if field.is_complex]

    @cached_property
    def _hash_field_names(self):
        return [field_name for field_name, field in self._fields.items() \
                if not field.is_complex]

    @cached_property
    def _complex_fields(self):
        return {field_name: field for field_name, field in self._fields.items() \
                if field.is_complex}

    @cached_property
    def _hash_fields(self):
        return {field_name: field for field_name, field in self._fields.items() \
                if not field.is_complex}

    @classmethod
    def drop_tree(cls):
        """Drops the entire tree associated with this
        :class:`~redisengine.BaseTreeCore` type from the database.
        """
        db = get_connection(cls._meta.db_alias)
        for key in db.scan_iter(cls._meta.tree_key_prefix + '*'):
            db.delete(key)

    def _delete(self):
        if not self._created and self._conn.delete(self.pk):
            dbg_msg = u"Deleted {}".format(self)
            assoc_fields = []
            for field_name, complex_field in self._complex_fields.items():
                field_operator = self._active_operators[field_name]
                if field_operator._delete():
                    assoc_fields.append(field_name)
            if assoc_fields:
                dbg_msg += u", together with the following associated fields: {}".format(assoc_fields)
            logger.debug(dbg_msg)
            return True

    def clean(self):
        """
        Hook for doing document level data cleaning before validation is run.
        Any ValidationError raised by this method will not be associated with
        a particular field; it will have a special-case association with the
        field defined by NON_FIELD_ERRORS.
        """
        pass

    def validate(self, fields=None, clean=True):
        errors = {}
        if clean:
            try:
                self.clean()
            except ValidationError, error:
                errors[NON_FIELD_ERRORS] = error

        # Get a list of tuples of field names and their current values
        if fields is None:
            fields = [(self._fields.get(name), getattr(self, name)) \
                      for name in self._fields_ordered]

        for field, value in fields:
            if value is not None:
                try:
                    field._validate(value)
                except ValidationError, error:
                    errors[field.name] = error.errors or error
                except (ValueError, AttributeError, AssertionError), error:
                    errors[field.name] = error
            elif field.required:
                errors[field.name] = ValidationError('Field is required',
                                                     field_name=field.name)

        if errors:
            try:
                pk = getattr(self, self.pk, "Unbound")
            except AttributeError:
                pk = "Unbound"
            message = "ValidationError (%s:%s) " % (self._class_name, pk)
            raise ValidationError(message, errors=errors)
