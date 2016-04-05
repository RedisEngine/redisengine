# -*- coding: utf-8 -*-
import sys
sys.path[0:0] = [""]
import unittest

from redisengine import fields
from redisengine.proxy.tree import ProxyTree
from redisengine.connection import connect, get_connection

__all__ = ("ClassMethodsTest", )

class ClassMethodsTest(unittest.TestCase):
    def setUp(self):
        connect(10)
        self.conn = get_connection()

        class Person(ProxyTree):
            name = fields.StringField()
            age = fields.IntField()

        self.Person = Person

    def tearDown(self):
        self.conn.flushdb()

    def test_definition(self):
        """Ensure that document may be defined using fields.
        """
        self.assertEqual(['age', 'name'], sorted(self.Person._fields.keys()))
        self.assertEqual(['IntField', 'StringField'],
                        sorted([x.__class__.__name__ for x in
                                self.Person._fields.values()]))

    def test_get_conn(self):
        """Ensure that get_connection returns the expected connection.
        """
        conn = get_connection(self.Person._meta.db_alias)
        self.assertEqual(self.conn, conn)



if __name__ == '__main__':
    unittest.main()
