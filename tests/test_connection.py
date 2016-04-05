import sys
import datetime

sys.path[0:0] = [""]

try:
    import unittest2 as unittest
except ImportError:
    import unittest
import redis

import redisengine.connection
from redisengine.proxy.tree import ProxyTree
from redisengine.connection import register_connection, connect, get_connection, ConnectionError


class ConnectionTest(unittest.TestCase):

    def tearDown(self):
        redisengine.connection._connection_settings = {}
        redisengine.connection._connections = {}
        redisengine.connection._dbs = {}

    def test_connect(self):
        """Ensure that the connect() method works properly.
        """
        connect(10, alias='redisenginetest')

        conn = get_connection('redisenginetest')
        self.assertTrue(isinstance(conn, redis.StrictRedis))

    def test_disconnect(self):
        """Ensure that the disconnect() method works properly
        """
        conn1 = connect(10, alias='redisenginetest')
        redisengine.connection.disconnect('redisenginetest')
        conn2 = connect(10, alias='redisenginetest')
        self.assertTrue(conn1 is not conn2)

    def test_sharing_connections(self):
        """Ensure that connections are shared when the connection settings are exactly the same
        """
        connect(10, alias='redisenginetests')
        expected_connection = get_connection('redisenginetests')

        connect(10, alias='redisenginetests')
        actual_connection = get_connection('redisenginetests')

        self.assertEqual(expected_connection, actual_connection)

    def test_register_connection(self):
        """Ensure that connections with different aliases may be registered.
        """
        register_connection('redisenginetest2', 10)
        self.assertRaises(ConnectionError, get_connection)
        conn = get_connection('redisenginetest2')
        self.assertTrue(isinstance(conn, redis.StrictRedis ))

    def test_register_connection_defaults(self):
        """Ensure that defaults are used when the host and port are None.
        """
        register_connection('redisenginetest', db=10, host=None, port=None)

        conn = get_connection('redisenginetest')
        self.assertTrue(isinstance(conn, redis.StrictRedis))

    def test_multiple_connection_settings(self):
        connect(10, alias='t1', host="localhost")

        connect(11, alias='t2', host="127.0.0.1")

        redis_connections = redisengine.connection._connections
        self.assertEqual(len(redis_connections.items()), 2)
        self.assertTrue('t1' in redis_connections.keys())
        self.assertTrue('t2' in redis_connections.keys())
        self.assertEqual(redis_connections['t1'].connection_pool.connection_kwargs['host'], 'localhost')
        self.assertEqual(redis_connections['t2'].connection_pool.connection_kwargs['host'], '127.0.0.1')


if __name__ == '__main__':
    unittest.main()
