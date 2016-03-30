import warnings

from redisengine.core.common import _tree_registry
from redisengine.core.fields import BaseField
from redisengine.core.manager import ProxyTreeManager, DirectTreeManager
from redisengine.proxy.base.tree import BaseProxyTree
from redisengine.connection import DEFAULT_CONNECTION_NAME
from redisengine.exceptions import InvalidTreeError, InvalidTreeWarning

class TreeMetaclass(type):

    allowed_names = ("id", "save", "validate", "clean")

    def __new__(cls, name, bases, attrs):
        super_new = super(TreeMetaclass, cls).__new__
        if attrs.get("__metaclass__") == cls:
            return super_new(cls, name, bases, attrs)

        if bases and issubclass(bases[0], BaseProxyTree):
            if hasattr(bases[0], "_meta"):
                raise ValueError("Cannot subclass {}".format(bases[0]))

            classes = bases[0].__base__.mro() + [bases[0]]
            reserved_attrs = {
                    attr for kls in classes \
                        for attr in dir(kls) \
                            if not attr.startswith("_") \
                            and not attr in cls.allowed_names}
            overlapping_attrs = set(attrs.keys()) & reserved_attrs
            if overlapping_attrs:
                raise InvalidTreeError("model `{}` defines illegal attributes/methods: {}".format(
                                        name, list(overlapping_attrs)))

        meta_attrs = {
            'tree_key_prefix': None,
            'tree_index_key': None,
            'pk_field_name': 'id',
            'has_auto_pk': True,
            'db_alias': DEFAULT_CONNECTION_NAME,
            # 'allow_overlapping_key_prefix': False,
            'ttl': None
        }

        field_names = {}
        doc_fields = {}

        def adjust_pk_index_name(tree_index_key):
            if not tree_index_key.startswith("__"):
                tree_index_key = "__" + tree_index_key.lower()
            if not tree_index_key.endswith(":idx"):
                tree_index_key += ":idx"
            return tree_index_key

        users_meta = attrs.get("Meta", None)
        if users_meta:
            # merge the two
            meta_attrs = {k: getattr(users_meta, k, v) for k, v in meta_attrs.iteritems()}

        meta_attrs['__slots__'] = meta_attrs.keys()
        meta = type("Meta", (object, ), meta_attrs)

        reserved = {attr for kls in classes for attr in dir(kls) if not attr=='id'}
        for field_name, field in attrs.iteritems():
            if not isinstance(field, BaseField):
                continue
            if field_name in reserved:
                raise InvalidTreeError("`{}` is not a valid name for a field".format(field_name))

            field.name = field_name
            if not field.db_field:
                field.db_field = field_name

            if hasattr(field, 'pk_type'):
                # field_name can only be `id` here
                if not field_name == "id":
                    raise InvalidTreeError("A field name for PrimaryKey can only be `id`")

                if issubclass(field.pk_type, str):
                    meta.has_auto_pk = False

                meta.tree_index_key = adjust_pk_index_name(field._prefix or name)
                meta.tree_key_prefix = name.lower()

            doc_fields[field_name] = field

            # Count names to ensure no db_field redefinitions
            field_names[field.db_field] = field_names.get(
                field.db_field, 0) + 1

        attrs.pop("id", None)

        # In case PrimaryKey wasn't defined
        if not meta.tree_key_prefix:
            meta.has_auto_pk = True
            meta.tree_key_prefix = name.lower()
            meta.tree_index_key = adjust_pk_index_name(meta.tree_index_key or name)

        # if meta.has_auto_pk:
        #     cls.establishPrefixIndex(
        #             meta.db_alias or DEFAULT_CONNECTION_NAME,
        #             meta.tree_index_key)
        attrs['_ttl'] = meta.ttl

        # Ensure no duplicate db_fields
        duplicate_db_fields = [k for k, v in field_names.items() if v > 1]
        if duplicate_db_fields:
            msg = ("Multiple db_fields defined for: %s " %
                   ", ".join(duplicate_db_fields))
            raise InvalidTreeError(msg)

        # Set _fields and db_field maps
        attrs['_fields'] = doc_fields
        attrs['_db_field_map'] = {k: getattr(v, 'db_field', k)\
                                       for k, v in doc_fields.iteritems()}

        attrs['_reverse_db_field_map'] = {v: k for k, v in attrs['_db_field_map'].iteritems() }
        attrs['_fields_ordered'] = tuple(i[1] for i in sorted(
                                        (v.creation_counter, v.name)
                                        for v in doc_fields.itervalues()))

        attrs['_class_name'] = name
        attrs['_meta'] = meta

        # Set a default proxy tree manager unless exists or one has been set
        if 'proxy_tree' not in dir(attrs):
            proxy_tree_manager = ProxyTreeManager
        else:
            assert issubclass(attrs['proxy_tree'], ProxyTreeManager)
            proxy_tree_manager = attrs['proxy_tree']
        attrs['proxy_tree'] = proxy_tree_manager(meta.tree_key_prefix)

        # Set a default direct tree manager unless exists or one has been set
        if 'direct_tree' not in dir(attrs):
            direct_tree_manager = DirectTreeManager
        else:
            assert issubclass(attrs['direct_tree'], DirectTreeManager)
            direct_tree_manager = attrs['direct_tree']
        attrs['direct_tree'] = direct_tree_manager(attrs.copy())

        new_class = super_new(cls, name, bases, attrs)

        # Add class to the _tree_registry
        _tree_registry[new_class._class_name] = new_class


        for field in new_class._fields.itervalues():
            if field.owner_tree is None:
                field.owner_tree = new_class

        return new_class
