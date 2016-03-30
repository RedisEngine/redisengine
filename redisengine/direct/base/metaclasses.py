import warnings
from functools import partial

from redisengine.exceptions import InvalidTreeWarning

__all__ = ("DirectTreeMetaclass", )

class DirectTreeMetaclass(type):
    def __new__(cls, name, bases, attrs):
        """Essentially, swap all set fields"""

        super_new = super(DirectTreeMetaclass, cls).__new__

        if attrs.get("__metaclass__") == cls:
            return super_new(cls, name, bases, attrs)

        # cls_name = attrs['_class_name']
        print attrs

        for field_name, field in attrs['_fields'].items():
            if hasattr(field, "pk_type"):
                print field, attrs.pop(field_name, None)
        #     # attrs.pop(field_name, None)
        #     try:
        #         operator = field.direct_operator
        #         # field.direct_operator = partial(operator, field)
        #     except AttributeError, e:
        #         print e
        #         warnings.warn(
        #             u"{}'s `{}` doesn't define `direct_operator` so it will be inaccessible".format(
        #                 cls_name, field_name),
        #             InvalidTreeWarning)
        #         del attrs[field_name]
        #         continue


            # attrs[field_name] = partial(operator, field)
            # attrs[field_name] = operator(field)

        attrs.pop("Meta", None)
        # return

        return super_new(cls, name, bases, attrs)
