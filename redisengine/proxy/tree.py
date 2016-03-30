from redisengine.exceptions import InvalidTreeError, LookUpError
from redisengine.core.common import _tree_registry
from redisengine.proxy.base.tree import BaseProxyTree
from redisengine.proxy.base.metaclasses import TreeMetaclass

__all__ = ["ProxyTree"]

class ProxyTree(BaseProxyTree):
    __metaclass__ = TreeMetaclass
    __slots__ = ('__objects',)

    def values(self, *keys, **kwargs):
        flat = kwargs.get("flat", False)
        if not self._created:
            keys = list(keys or self._fields_ordered)
            # if 'id' in keys:
            #     idx = keys.index('id')
            #     keys[idx] = 'pk'
            try:
                keys.remove('id')
                keys.remove('pk')
            except ValueError:
                pass
            if flat:
                return [getattr(self, key) for key in keys]
            return {key: getattr(self, key) for key in keys}

    def save(self, validate=True, clean=True, use=None, ttl=None, **kwargs):
        """
        :param validate: validates the document; set to ``False`` to skip.
        :param clean: call the document clean method, requires `validate` to be True.
        :param use: optionally write to a different, pre-registered Redis db
        :param ttl: Time to live for the field as a value in seconds to use for the EXPIRY command.
        return an id of a created/updated record

        """
        try:
            ttl = int(ttl or self._ttl)
        except:
            ttl = None

        if validate:
            self.validate(clean=clean)

        # tree_data = self.to_redis()
        if self._created:
            id = self.perform_create(ttl, **kwargs)
        else:
            id = self.perform_update()

        self._clear_changed_fields()
        return id

    def delete(self):
        if self._delete():
            # reset all values
            self._setValues(values=dict.fromkeys(self._fields))
            self._created = True
            del self._changed_fields
            del self._deleted_fields
