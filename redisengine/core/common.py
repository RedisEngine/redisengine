from redisengine.exceptions import NotRegistered

__all__ = ('ALLOW_INHERITANCE', 'get_tree', '_tree_registry')

ALLOW_INHERITANCE = False

_tree_registry = {}


def get_tree(name):
    doc = _tree_registry.get(name, None)
    if not doc:
        # Possible old style name
        single_end = name.split('.')[-1]
        compound_end = '.%s' % single_end
        possible_match = [k for k in _tree_registry.keys()
                          if k.endswith(compound_end) or k == single_end]
        if len(possible_match) == 1:
            doc = _tree_registry.get(possible_match.pop(), None)
    if not doc:
        raise NotRegistered("""
            `%s` has not been registered in the tree registry.
            Importing the tree class automatically registers it, has it
            been imported?
        """.strip() % name)
    return doc
