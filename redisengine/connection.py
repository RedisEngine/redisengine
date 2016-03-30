from redis import StrictRedis

__all__ = ['ConnectionError', 'connect', 'register_connection', 'get_connection',
           'DEFAULT_CONNECTION_NAME']


DEFAULT_CONNECTION_NAME = 'default'

class ConnectionError(Exception):
    pass

_connection_settings = {}
_connections = {}

def register_connection(alias, db=0, host=None, port=None,
                         password=None, **kwargs):
    """Add a connection.
    :param alias: the name that will be used to refer to this connection
        throughout RedisEngine
    :param db: the index of the specific database to use.
    :param host: the host name of the :program:`mongod` instance to connect to
    :param port: the port that the :program:`mongod` instance is running on
    :param password: password to authenticate with
    :param kwargs: allow ad-hoc parameters to be passed into the redis driver
    """
    global _connection_settings
    try:
        int(db)
    except:
        raise TypeError("`db` index needs to be of `int` type")

    conn_settings = {
        'db': db or 0,
        'host': host or 'localhost',
        'port': port or 6379,
        'password': password,
    }

    conn_settings.update(kwargs)
    _connection_settings[alias] = conn_settings


def disconnect(alias=DEFAULT_CONNECTION_NAME):
    global _connections

    if alias in _connections:
        get_connection(alias=alias).connection_pool.disconnect()
        del _connections[alias]

def get_connection(alias=DEFAULT_CONNECTION_NAME, reconnect=False):
    global _connections
    # Connect to the database if not already connected
    if reconnect:
        disconnect(alias)

    if alias not in _connections:
        if alias not in _connection_settings:
            msg = 'Connection with alias "%s" has not been defined' % alias
            if alias == DEFAULT_CONNECTION_NAME:
                msg = 'You have not defined a default connection'
            raise ConnectionError(msg)
        conn_settings = _connection_settings[alias].copy()
        connection_class = StrictRedis

        try:
            connection = None
            # check for shared connections
            connection_settings_iterator = (
                (db_alias, settings.copy()) for db_alias, settings in _connection_settings.iteritems())
            for db_alias, connection_settings in connection_settings_iterator:
                if conn_settings == connection_settings and _connections.get(db_alias, None):
                    connection = _connections[db_alias]
                    break

            _connections[alias] = connection if connection else connection_class(**conn_settings)

        except Exception, e:
            raise ConnectionError("Cannot connect to database %s :\n%s" % (alias, e))
    return _connections[alias]

def connect(db=0, alias=DEFAULT_CONNECTION_NAME, **kwargs):
    """Connect to the database specified by the 'db' argument.
    Connection settings may be provided here as well if the database is not
    running on the default port on localhost. If authentication is needed,
    provide password argument as well.
    Multiple databases are supported by using aliases.
    """
    global _connections
    if alias not in _connections:
        register_connection(alias, db, **kwargs)

    return get_connection(alias)
