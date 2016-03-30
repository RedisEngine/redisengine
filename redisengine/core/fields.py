import warnings
import weakref

from redisengine.exceptions import ValidationError

__all__ = ("BaseField", "BaseComplexField")


UPDATE_OPERATORS = set(['set', 'unset', 'inc', 'dec', 'pop', 'push',
                        'push_all', 'pull', 'pull_all', 'add_to_set',
                        'set_on_insert', 'min', 'max'])


class BaseField(object):
    """A base class for fields in a Redis Hash. Instances of this class
    may be added to subclasses of `Tree` to define a tree's schema.
    """

    name = None
    creation_counter = 0
    auto_creation_counter = -1
    proxy_operator = None
    direct_operator = None
    is_complex = False
    # active_operator = None # set to either proxy_operator or direct_operator by, well, one of them

    def __init__(self, db_field=None, required=False, default=None,
                 unique=False, validation=None, choices=None,
                 null=False, sparse=False, **kwargs):
        """
        :param db_field: The database field to store this field in
            (defaults to the name of the field)
        :param required: If the field is required. Whether it has to have a
            value or not. Defaults to False.
        :param default: (optional) The default value for this field if no value
            has been set (or if the value has been unset).  It can be a
            callable.
        :param unique: Is the field value unique or not.  Defaults to False.
        :param validation: (optional) A callable to validate the value of the
            field.  Generally this is deprecated in favour of the
            `FIELD.validate` method
        :param choices: (optional) The valid choices
        :param null: (optional) Is the field value can be null. If no and there is a default value
            then the default value is set
        :param sparse: (optional) `sparse=True` combined with `unique=True` and `required=False`
            means that uniqueness won't be enforced for `None` values
        :param **kwargs: (optional) Arbitrary indirection-free metadata for
            this field can be supplied as additional keyword arguments and
            accessed as attributes of the field. Must not conflict with any
            existing attributes. Common metadata includes `verbose_name` and
            `help_text`.
        """
        self.db_field = db_field
        self.required = required
        self.default = default
        self.unique = unique
        self.validation = validation
        self.choices = choices
        self.null = null
        self.sparse = sparse
        self._owner_tree = None

        if self.db_field == '_id':
            self.creation_counter = BaseField.auto_creation_counter
            BaseField.auto_creation_counter -= 1
        else:
            self.creation_counter = BaseField.creation_counter
            BaseField.creation_counter += 1

        # Detect and report conflicts between metadata and base properties.
        conflicts = set(dir(self)) & set(kwargs)
        if conflicts:
            raise TypeError("%s already has attribute(s): %s" % (
                self.__class__.__name__, ', '.join(conflicts) ))

        # Assign metadata to the instance
        # This efficient method is available because no __slots__ are defined.
        self.__dict__.update(kwargs)

    def __get__(self, instance, owner):
        if instance is None:
            return self

        operator = instance._active_operators[self.name]
        try:
            return operator._value
        except AttributeError:
            return operator

    def __delete__(self, instance):
        adjusted_value = self.adjustValue(None)
        instance._operator_deleter(self.name, adjusted_value)

    def __set__(self, instance, value):
        value = self.adjustValue(value)
        return instance._operator_setter(self.name, value)

    def adjustValue(self, value):
        if value is None:
            if self.null:
                value = None
            elif self.default is not None:
                value = self.default
                if callable(value):
                    value = value()
            else:
                try:
                    value = self.redis_type()
                except AttributeError:
                    pass
        else:
            self.checkType(value)

        return value

    def checkType(self, value):
        """Raise TypeError if value isn't of `redis_type` type"""
        pass

    def error(self, message="", errors=None, field_name=None):
        """Raises a ValidationError.
        """
        field_name = field_name if field_name else self.name
        raise ValidationError(message, errors=errors, field_name=field_name)

    def to_python(self, value):
        try:
            value = self.redis_type(value)
        except ValueError:
            pass
        except TypeError:
            return self.redis_type()
        return value

    def to_redis(self, value, **kwargs):
        """Convert a Python type to a Redis-compatible type.
        """
        return self.to_python(value)

    def validate(self, value, clean=True):
        """Perform validation on a value.
        """
        pass

    def _validate_choices(self, value):
        pass
        # Document = _import_class('Document')
        # EmbeddedDocument = _import_class('EmbeddedDocument')

        # choice_list = self.choices
        # if isinstance(choice_list[0], (list, tuple)):
        #     choice_list = [k for k, _ in choice_list]

        # # Choices which are other types of Documents
        # if isinstance(value, (Document, EmbeddedDocument)):
        #     if not any(isinstance(value, c) for c in choice_list):
        #         self.error(
        #             'Value must be instance of %s' % unicode(choice_list)
        #         )
        # # Choices which are types other than Documents
        # elif value not in choice_list:
        #     self.error('Value must be one of %s' % unicode(choice_list))
    def checkType(self, value):
        return value

    def _validate(self, value, **kwargs):
        # Check the Choices Constraint
        if self.choices:
            self._validate_choices(value)

        # check validation argument
        if self.validation is not None:
            if callable(self.validation):
                if not self.validation(value):
                    self.error('Value does not match custom validation method')
            else:
                raise ValueError('validation argument for "%s" must be a '
                                 'callable.' % self.name)

        self.validate(value, **kwargs)

    @property
    def owner_tree(self):
        return self._owner_tree

    def _set_owner_tree(self, owner_tree):
        self._owner_tree = owner_tree

    @owner_tree.setter
    def owner_tree(self, owner_tree):
        self._set_owner_tree(owner_tree)


class BaseNumberField(BaseField):
    def __init__(self, min_value=None, max_value=None, **kwargs):
        self.min_value, self.max_value = min_value, max_value
        super(BaseNumberField, self).__init__(**kwargs)


    def validate(self, value):
        try:
            value = self.redis_type(value)
        except:
            self.error('{} could not be converted to {}'.format(
                        value, self.redis_type.__name__))

        if self.min_value is not None and value < self.min_value:
            self.error('Value is too small')

        if self.max_value is not None and value > self.max_value:
            self.error('Value is too large')


class BaseComplexField(BaseField):
    """
    A base class to support Redis' List, Set, Hash and Sorted Set types.
    """
    # TODO:
    # - pickling/unpickling through Redis' message pack
    redis_type = None
    child_field = None
    is_complex = True

    def __init__(self, child_field=None, field_affix=None, **kwargs):
        """
        :param child_field: BaseField's intance of an intended ComplexField member
        :param field_affix: Affix for the field's key
        """

        if self.redis_type is None:
            raise ValueError("`redis_type` has to define a type")

        if child_field:
            assert isinstance(child_field, BaseField), \
                "`child_field` must be an instance of BaseField, not {}".format(
                child_field.__class__.__name__)
            self.child_field = child_field

        self.field_affix = field_affix or self.name
        super(BaseComplexField, self).__init__(**kwargs)

    def checkType(self, value):
        if not isinstance(value, self.redis_type):
            raise TypeError("Can't set type {0.__class__.__name__} to field `{1.name}`. Accepts only {2.__name__}".format(
                value, self, self.redis_type
            ))

    def item_to_redis(self, item, **kwargs):
        return self.child_field.to_redis(item, **kwargs)

    def item_to_python(self, item, **kwargs):
        return self.child_field.to_python(item, **kwargs)

    def validate_item(self, item, **kwargs):
        self.child_field.validate(item, **kwargs)

    def _validate(self, value, **kwargs):
        if not value and self.required:
            self.error('Field is required')
        return super(BaseComplexField, self)._validate(value, **kwargs)
