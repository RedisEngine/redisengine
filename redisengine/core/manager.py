from functools import partial
from itertools import izip
from redisengine.connection import get_connection
from redisengine.direct.tree import DirectTree
from redisengine.exceptions import DoesNotExist

__all__ = ("DirectTreeManager", "ProxyTreeManager")

class ProxyTreeQuerySet(object):
    def __init__(self, conn, owner, tree_pk_prefix=None):
        self.conn = conn
        self.owner = owner
        self.tree_pk_prefix = tree_pk_prefix

    def __call__(self, id, **kwargs):
        only = kwargs.get('only', [])
        inst_pk = ":".join((self.tree_pk_prefix, str(id)))
        if not any(self.conn.scan_iter(inst_pk + "*")):
            raise DoesNotExist("Tree with pk {} not found".format(inst_pk))

        # fetch hash keys associated with this tree
        if only:
            tree_data = {key: value for key, value in \
                    izip(only, self.conn.hmget(inst_pk, *only)) if value}
        else:
            tree_data = dict(self.conn.hscan_iter(inst_pk))

        tree_data['pk'] = str(id)
        return self.owner._instantiate(data=tree_data, **kwargs)

    def all(self):
        for pk in self.conn.scan_iter(self.owner._meta.tree_key_prefix + "*"):
            id = pk.split(":", 1)[1]
            if ":" not in id:
                yield self(id)


class BaseTreeManager(object):
    qs_stash = {}
    def __init__(self, tree_pk_prefix):
        self.tree_pk_prefix = tree_pk_prefix

    def __get__(self, instance, owner):
        """
        Descriptor for instantiating a new TreeSet object when
        Tree.tree is accessed.
        """
        if instance is not None:
            # Document class being used rather than a document object
            raise AttributeError("TreeManager isn't accessible via Tree instances.")
        if not self.qs_stash.has_key(id(owner)):
            conn = get_connection(alias=owner._meta.db_alias)
            self.qs_stash[id(owner)] = tree = self.get_tree_class(conn, owner)
            return tree

        return self.qs_stash[id(owner)]

    def get_tree_class(self, conn, owner):
        raise NotImplementedError()


class ProxyTreeManager(BaseTreeManager):
    def get_tree_class(self, conn, owner):
        return ProxyTreeQuerySet(conn, owner, tree_pk_prefix=self.tree_pk_prefix)


class DirectTreeManager(BaseTreeManager):
    def __init__(self, attrs):
        self.direct_tree_cls = type(attrs['_class_name'], (DirectTree, ), attrs)

    def get_tree_class(self, conn, owner):
        return partial(self.direct_tree_cls, conn=conn)
