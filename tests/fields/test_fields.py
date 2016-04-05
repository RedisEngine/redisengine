# -*- coding: utf-8 -*-
import sys
from nose.plugins.skip import SkipTest

sys.path[0:0] = [""]

import time
import unittest
import uuid
import math
import itertools
import re

try:
    import dateutil
except ImportError:
    dateutil = None

from decimal import Decimal

from redisengine import fields
from redisengine import exceptions
from redisengine.connection import connect, get_connection
from redisengine.proxy.tree import ProxyTree


__all__ = ("FieldTest", )


class FieldTest(unittest.TestCase):
    def setUp(self):
        connect(10)
        self.conn = get_connection()

    def tearDown(self):
        self.conn.flushdb()

    def test_default_values_nothing_set(self):
        """Ensure that default field values are used when creating a tree.
        """
        class Person(ProxyTree):
            name = fields.StringField()
            age = fields.IntField(default=30, required=False)
            userid = fields.StringField(default=lambda: 'test', required=True)
            created = fields.IntField(default=lambda: int(time.time()))

        person = Person(name="Ross")
        person._acquire_pk()

        # Confirm saving now would store values
        data_to_be_saved = sorted(person.to_redis()['tree'].keys())
        self.assertEqual(
            data_to_be_saved, ['age', 'created', 'name', 'userid'])

        self.assertTrue(person.validate() is None)

        self.assertEqual(person.name, person.name)
        self.assertEqual(person.age, person.age)
        self.assertEqual(person.userid, person.userid)
        self.assertEqual(person.created, person.created)

        self.assertEqual(person._active_operators['name']._value, person.name)
        self.assertEqual(person._active_operators['age']._value, person.age)
        self.assertEqual(person._active_operators['userid']._value, person.userid)
        self.assertEqual(person._active_operators['created']._value, person.created)

        # # Confirm introspection changes nothing
        data_to_be_saved = sorted(person.to_redis()['tree'].keys())
        self.assertEqual(
            data_to_be_saved, ['age', 'created', 'name', 'userid'])


    def test_default_values_set_to_None(self):
        """Ensure that default field values are used when creating a tree.
        """
        class Person(ProxyTree):
            name = fields.StringField(null=True)
            age = fields.IntField(default=30, required=False)
            userid = fields.StringField(default=lambda: 'test', required=True)
            created = fields.IntField(default=lambda: int(time.time()))

        # Trying setting values to None
        person = Person(name=None, age=None, userid=None, created=None)
        person._acquire_pk()

        # Confirm saving now would store values
        data_to_be_saved = sorted(person.to_redis()['tree'].keys())
        self.assertEqual(data_to_be_saved, ['age', 'created', 'userid'])

        self.assertTrue(person.validate() is None)

        self.assertEqual(person.name, person.name)
        self.assertEqual(person.age, person.age)
        self.assertEqual(person.userid, person.userid)
        self.assertEqual(person.created, person.created)

        self.assertEqual(person._active_operators['name']._value, person.name)
        self.assertEqual(person._active_operators['age']._value, person.age)
        self.assertEqual(person._active_operators['userid']._value, person.userid)
        self.assertEqual(person._active_operators['created']._value, person.created)

        # Confirm introspection changes nothing
        data_to_be_saved = sorted(person.to_redis()['tree'].keys())
        self.assertEqual(data_to_be_saved, ['age', 'created', 'userid'])

    def test_default_values_when_setting_to_None(self):
        """Ensure that default field values are used when creating a tree.
        """
        class Person(ProxyTree):
            name = fields.StringField(null=True)
            age = fields.IntField(default=30, required=False)
            userid = fields.StringField(default=lambda: 'test', required=True)
            created = fields.IntField(default=lambda: int(time.time()))


        person = Person()
        person._acquire_pk()
        person.name = None
        person.age = None
        person.userid = None
        person.created = None

        # Confirm saving now would store values
        data_to_be_saved = sorted(person.to_redis()['tree'].keys())
        self.assertEqual(data_to_be_saved, ['age', 'created', 'userid'])

        self.assertTrue(person.validate() is None)

        self.assertEqual(person.name, person.name)
        self.assertEqual(person.age, person.age)
        self.assertEqual(person.userid, person.userid)
        self.assertEqual(person.created, person.created)

        self.assertEqual(person._active_operators['name']._value, person.name)
        self.assertEqual(person._active_operators['age']._value, person.age)
        self.assertEqual(person._active_operators['userid']._value, person.userid)
        self.assertEqual(person._active_operators['created']._value, person.created)

        # Confirm introspection changes nothing
        data_to_be_saved = sorted(person.to_redis()['tree'].keys())
        self.assertEqual(data_to_be_saved, ['age', 'created', 'userid'])

    def test_default_values_when_deleting_value(self):
        """Ensure that default field values are used when creating a tree.
        """
        class Person(ProxyTree):
            name = fields.StringField(null=True)
            age = fields.IntField(default=30, required=False)
            userid = fields.StringField(default=lambda: 'test', required=True)
            created = fields.IntField(default=lambda: int(time.time()))

        person = Person(name="Ross")
        person._acquire_pk()
        del person.name
        del person.age
        del person.userid
        del person.created

        data_to_be_saved = sorted(person.to_redis()['tree'].keys())
        self.assertEqual(data_to_be_saved, ['age', 'created', 'userid'])

        self.assertTrue(person.validate() is None)

        self.assertEqual(person.name, person.name)
        self.assertEqual(person.age, person.age)
        self.assertEqual(person.userid, person.userid)
        self.assertEqual(person.created, person.created)

        self.assertEqual(person._active_operators['name']._value, person.name)
        self.assertEqual(person._active_operators['age']._value, person.age)
        self.assertEqual(person._active_operators['userid']._value, person.userid)
        self.assertEqual(person._active_operators['created']._value, person.created)

        # Confirm introspection changes nothing
        data_to_be_saved = sorted(person.to_redis()['tree'].keys())
        self.assertEqual(data_to_be_saved, ['age', 'created', 'userid'])

    def test_required_values(self):
        """Ensure that required field constraints are enforced.
        """
        class Person(ProxyTree):
            name = fields.StringField(required=True)
            age = fields.IntField(required=True)
            userid = fields.StringField()

        person = Person(name="Test User")
        self.assertRaises(exceptions.ValidationError, person.validate)
        person = Person(age=30)
        self.assertRaises(exceptions.ValidationError, person.validate)

    def test_string_validation(self):
        """Ensure that invalid values cannot be assigned to string fields.
        """
        class Person(ProxyTree):
            name = fields.StringField(max_length=20)
            userid = fields.StringField(r'[0-9a-z_]+$')

        person = Person(name=34)
        self.assertRaises(exceptions.ValidationError, person.validate)

        # Test regex validation on userid
        person = Person(userid='test.User')
        self.assertRaises(exceptions.ValidationError, person.validate)

        person.userid = 'test_user'
        self.assertEqual(person.userid, 'test_user')
        person.validate()

        # Test max length validation on name
        person = Person(name='Name that is more than twenty characters')
        self.assertRaises(exceptions.ValidationError, person.validate)

        person.name = 'Shorter name'
        person.validate()

    def test_url_validation(self):
        """Ensure that URLFields validate urls properly.
        """
        class Link(ProxyTree):
            url = fields.URLField()

        link = Link()
        link.url = 'google'
        self.assertRaises(exceptions.ValidationError, link.validate)

        link.url = 'http://www.google.com:8080'
        link.validate()

    def test_url_scheme_validation(self):
        """Ensure that URLFields validate urls with specific schemes properly.
        """
        class Link(ProxyTree):
            url = fields.URLField()

        class SchemeLink(ProxyTree):
            url = fields.URLField(schemes=['ws', 'irc'])

        link = Link()
        link.url = 'ws://google.com'
        self.assertRaises(exceptions.ValidationError, link.validate)

        scheme_link = SchemeLink()
        scheme_link.url = 'ws://google.com'
        scheme_link.validate()

    def test_int_validation(self):
        """Ensure that invalid values cannot be assigned to int fields.
        """
        class Person(ProxyTree):
            age = fields.IntField(min_value=0, max_value=110)

        person = Person()
        person.age = 50
        person.validate()

        person.age = -1
        self.assertRaises(exceptions.ValidationError, person.validate)
        person.age = 120
        self.assertRaises(exceptions.ValidationError, person.validate)
        person.age = 'ten'
        self.assertRaises(exceptions.ValidationError, person.validate)

    def test_float_validation(self):
        """Ensure that invalid values cannot be assigned to float fields.
        """
        class Person(ProxyTree):
            height = fields.FloatField(min_value=0.1, max_value=3.5)

        person = Person()
        person.height = 1.89
        person.validate()

        person.height = 0.01
        self.assertRaises(exceptions.ValidationError, person.validate)
        person.height = 4.0
        self.assertRaises(exceptions.ValidationError, person.validate)

        person_2 = Person(height='something invalid')
        self.assertRaises(exceptions.ValidationError, person_2.validate)

    def test_list_validation(self):
        """Ensure that a list field only accepts lists with valid elements.
        """

        class BlogPost(ProxyTree):
            content = fields.StringField()
            comments = fields.ListField(fields.StringField())
            tags = fields.ListField(fields.StringField())

        post = BlogPost(content='Went for a walk today...')
        post.validate()

        # post.tags = 'fun'
        # self.assertRaises(exceptions.ValidationError, post.validate)
        post.tags = [1, 2]
        self.assertRaises(exceptions.ValidationError, post.validate)

        post.tags = ['fun', 'leisure']
        post.validate()
        # post.tags = ('fun', 'leisure')
        # post.validate()

        def set_comments():
            post.comments = 'yay'
        self.assertRaises(TypeError, set_comments)

        BlogPost.drop_tree()




if __name__ == '__main__':
    unittest.main()
