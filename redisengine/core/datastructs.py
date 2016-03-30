import itertools
from zlib import crc32
from redisengine.exceptions import DoesNotExist, MultipleObjectsReturned

__all__ = ("StrictDict", "SemiStrictDict")

class StrictDict(object):
    __slots__ = ()
    _special_fields = set(['get', 'pop', 'iteritems', 'items', 'keys', 'create'])
    _classes = {}

    def __init__(self, **kwargs):
        for k, v in kwargs.iteritems():
            setattr(self, k, v)

    def __getitem__(self, key):
        key = '_reserved_' + key if key in self._special_fields else key
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key)

    def __setitem__(self, key, value):
        key = '_reserved_' + key if key in self._special_fields else key
        return setattr(self, key, value)

    def __contains__(self, key):
        return hasattr(self, key)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def pop(self, key, default=None):
        v = self.get(key, default)
        try:
            delattr(self, key)
        except AttributeError:
            pass
        return v

    def iteritems(self):
        for key in self:
            yield key, self[key]

    def items(self):
        return [(k, self[k]) for k in iter(self)]

    def iterkeys(self):
        return iter(self)

    def keys(self):
        return list(iter(self))

    def __iter__(self):
        return (key for key in self.__slots__ if hasattr(self, key))

    def __len__(self):
        return len(list(self.iteritems()))

    def __eq__(self, other):
        return self.items() == other.items()

    def __neq__(self, other):
        return self.items() != other.items()

    @classmethod
    def create(cls, allowed_keys, complex_data={}):
        allowed_keys_tuple = tuple(('_reserved_' + k if k in cls._special_fields else k) for k in allowed_keys)
        allowed_keys = frozenset(allowed_keys_tuple)
        if allowed_keys not in cls._classes:
            complex_keys_hashes = {k: crc32(repr(v)) for k, v in complex_data.items()}
            class SpecificStrictDict(cls):
                __slots__ = allowed_keys_tuple

                @property
                def _changed_complex_fields(self):
                    for key, val in complex_keys_hashes.items():
                        print self[key], val
                    d = {
                        k: self[k] for k, v in complex_keys_hashes.items() \
                        if v != crc32(repr(self[k]))
                    }
                    return d

                def __repr__(self):
                    return "{%s}" % ', '.join('"{0!s}": {0!r}'.format(k) for k in self.iterkeys())

            cls._classes[allowed_keys] = SpecificStrictDict
        return cls._classes[allowed_keys]


class SemiStrictDict(StrictDict):
    __slots__ = ('_extras', )
    _classes = {}

    def __getattr__(self, attr):
        try:
            super(SemiStrictDict, self).__getattr__(attr)
        except AttributeError:
            try:
                return self.__getattribute__('_extras')[attr]
            except KeyError as e:
                raise AttributeError(e)

    def __setattr__(self, attr, value):
        try:
            super(SemiStrictDict, self).__setattr__(attr, value)
        except AttributeError:
            try:
                self._extras[attr] = value
            except AttributeError:
                self._extras = {attr: value}

    def __delattr__(self, attr):
        try:
            super(SemiStrictDict, self).__delattr__(attr)
        except AttributeError:
            try:
                del self._extras[attr]
            except KeyError as e:
                raise AttributeError(e)

    def __iter__(self):
        try:
            extras_iter = iter(self.__getattribute__('_extras'))
        except AttributeError:
            extras_iter = ()
        return itertools.chain(super(SemiStrictDict, self).__iter__(), extras_iter)
