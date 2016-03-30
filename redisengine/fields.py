import re
import cPickle
import warnings
import urllib2

from redisengine.core.fields import BaseField, BaseComplexField, BaseNumberField
from redisengine.direct import operators as direct_operators
from redisengine.proxy import operators as proxy_operators

__all__ = ['StringField', "IntField",
            "ListField", "SetField",
            "AutoPrimaryKey", "StringPrimaryKey"]

class HashField(BaseField):
    redis_type = str
    direct_operator = direct_operators.HashOperator
    proxy_operator = proxy_operators.HashOperator


class StringField(HashField):
    def __init__(self, regex=None, max_length=None, min_length=None, **kwargs):
        self.regex = re.compile(regex) if regex else None
        self.max_length = max_length
        self.min_length = min_length
        super(StringField, self).__init__(**kwargs)

    def to_python(self, value):
        if isinstance(value, unicode):
            return value
        try:
            value = value.decode('utf-8')
        except:
            pass
        return value

    def validate(self, value):
        if not isinstance(value, basestring):
            self.error('StringField only accepts string values')

        if self.max_length is not None and len(value) > self.max_length:
            self.error('String value is too long')

        if self.min_length is not None and len(value) < self.min_length:
            self.error('String value is too short')

        if self.regex is not None and self.regex.match(value) is None:
            self.error('String value did not match validation regex')


class IntField(BaseNumberField):
    """An 32-bit integer field.
    """
    redis_type = int
    direct_operator = direct_operators.IntegerOperator
    proxy_operator = proxy_operators.HashOperator


class FloatField(BaseNumberField):
    redis_type = float
    direct_operator = direct_operators.FloatOperator
    proxy_operator = proxy_operators.HashOperator


class AutoPrimaryKey(HashField):
    pk_type = int

    def __init__(self, prefix=None):
        self._prefix = prefix
        kwargs = {'db_field': "id"}
        super(AutoPrimaryKey, self).__init__(**kwargs)

    def validate(self, value):
        if not isinstance(value, self.pk_type):
            self.error("Value provided to PrimaryKey field of wrong type")

class StringPrimaryKey(AutoPrimaryKey):
    pk_type = str

class BooleanField(HashField):
    redis_type = bool

    def to_python(self, value):
        try:
            return bool(int(value))
        except ValueError:
            return None

    def to_redis(self, value, **k):
        try:
            return int(value)
        except ValueError:
            return 0


class ListField(BaseComplexField):
    redis_type = list
    proxy_operator = proxy_operators.ListOperator
    direct_operator = direct_operators.ListOperator

    def to_python(self, value):
        if self.child_field:
            return [self.item_to_python(item) for item in value]
        try:
            return [cPickle.loads(item) for item in value]
        except (cPickle.UnpicklingError, ValueError):
            return value

    def to_redis(self, value, **kwargs):
        if self.child_field:
            return [self.item_to_redis(item, **kwargs) for item in value]
        # this is the only way to retain the original values
        return [cPickle.dumps(item) for item in value]

    def validate(self, value, **kwargs):
        if self.child_field:
            for item in value:
                self.validate_item(item, **kwargs)

class SetField(BaseComplexField):
    redis_type = set
    proxy_operator = proxy_operators.SetOperator

    def to_python(self, value):
        if self.child_field:
            return {self.item_to_python(item) for item in value}
        try:
            return {cPickle.loads(item) for item in value}
        except cPickle.UnpicklingError:
            return value

    def to_redis(self, value, **kwargs):
        if self.child_field:
            return {self.item_to_redis(item, **kwargs) for item in value}
        return [cPickle.dumps(item) for item in value]

    def validate(self, value, **kwargs):
        if self.child_field:
            for item in value:
                self.validate_item(item, **kwargs)

class DomainField(StringField):
    def __init__(self, **kwargs):
        super(DomainField, self).__init__(**kwargs)
        self.max_length = None
        self.min_length = None
        # taken from http://stackoverflow.com/questions/10306690/domain-name-validation-with-regex#answer-20046959
        self.regex = re.compile(
            r'^(([a-zA-Z]{1})|([a-zA-Z]{1}[a-zA-Z]{1})|([a-zA-Z]{1}[0-9]{1})|([0-9]{1}[a-zA-Z]{1})|([a-zA-Z0-9][a-zA-Z0-9-_]{1,61}[a-zA-Z0-9]))\.([a-zA-Z]{2,6}|[a-zA-Z0-9-]{2,30}\.[a-zA-Z]{2,3})$')


class URLField(StringField):
    """A field that validates input as an URL.
    """

    _URL_REGEX = re.compile(
        r'^(?:[a-z0-9\.\-]*)://'  # scheme is validated separately
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}(?<!-)\.?)|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|'  # ...or ipv4
        r'\[?[A-F0-9]*:[A-F0-9:]+\]?)'  # ...or ipv6
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    _URL_SCHEMES = ['http', 'https', 'ftp', 'ftps']

    def __init__(self, verify_exists=False, url_regex=None, schemes=None, **kwargs):
        self.verify_exists = verify_exists
        self.url_regex = url_regex or self._URL_REGEX
        self.schemes = schemes or self._URL_SCHEMES
        super(URLField, self).__init__(**kwargs)

    def validate(self, value):
        # Check first if the scheme is valid
        scheme = value.split('://')[0].lower()
        if scheme not in self.schemes:
            self.error('Invalid scheme {} in URL: {}'.format(scheme, value))
            return

        # Then check full URL
        if not self.url_regex.match(value):
            self.error('Invalid URL: {}'.format(value))
            return

        if self.verify_exists:
            warnings.warn(
                "The URLField verify_exists argument has intractable security "
                "and performance issues. Accordingly, it has been deprecated.",
                DeprecationWarning)
            try:
                request = urllib2.Request(value)
                urllib2.urlopen(request)
            except Exception, e:
                self.error('This URL appears to be a broken link: %s' % e)


class EmailField(StringField):
    """A field that validates input as an E-Mail-Address.
    """

    EMAIL_REGEX = re.compile(
        # dot-atom
        r"(^[-!#$%&'*+/=?^_`{}|~0-9A-Z]+(\.[-!#$%&'*+/=?^_`{}|~0-9A-Z]+)*"
        # quoted-string
        r'|^"([\001-\010\013\014\016-\037!#-\[\]-\177]|\\[\001-011\013\014\016-\177])*"'
        # domain (max length of an ICAAN TLD is 22 characters)
        r')@(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}|[A-Z0-9-]{2,}(?<!-))$', re.IGNORECASE
    )

    def validate(self, value):
        if not EmailField.EMAIL_REGEX.match(value):
            self.error('Invalid Mail-address: %s' % value)
        super(EmailField, self).validate(value)
