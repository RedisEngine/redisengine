# -*- coding: utf-8 -*-
import sys
sys.path[0:0] = [""]
import unittest

from redisengine import fields
from redisengine.proxy.tree import ProxyTree
from redisengine.connection import connect, get_connection

__all__ = ("DeltaTest",)


class DeltaTest(unittest.TestCase):
    def setUp(self):
        connect(10)
        self.conn = get_connection()

        class Person(ProxyTree):
            name = fields.StringField()
            age = fields.IntField()

        self.Person = Person

    def tearDown(self):
        self.conn.flushdb()

    def test_delta(self):
        class Doc(ProxyTree):
            string_field = fields.StringField()
            int_field = fields.IntField()
            list_field = fields.ListField()

        Doc.drop_tree()
        doc = Doc()
        doc.string_field = 'dfg'
        did = doc.save()

        doc = Doc.proxy_tree(did)
        self.assertEqual(doc._changed_fields, [])

        doc.string_field = 'hello'
        self.assertEqual(doc._changed_fields, ['string_field'])

        doc._changed_fields = []
        doc.int_field = 1
        self.assertEqual(doc._changed_fields, ['int_field'])

        doc._changed_fields = []
        list_value = ['1', 2, {'hello': 'world'}]
        doc.list_field = list_value
        self.assertEqual(doc._changed_fields, ['list_field'])

        id_doc = doc.save()
        doc.list_field.append(23423)
        self.assertEqual(doc._changed_fields, ['list_field'])


if __name__ == '__main__':
    unittest.main()
