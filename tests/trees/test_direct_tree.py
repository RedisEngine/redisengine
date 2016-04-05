# -*- coding: utf-8 -*-
import sys
import cPickle
from functools import partial
from nose.plugins.skip import SkipTest

sys.path[0:0] = [""]

import time
import unittest
import uuid
import math
import re

from redisengine import fields
from redisengine import exceptions
from redisengine.connection import connect, get_connection
from redisengine.direct.tree import DirectTree
from redisengine.proxy.tree import ProxyTree

__all__ = ("TestDirectTree", )

class TestDirectTree(unittest.TestCase):
    def setUp(self):
        connect(10)
        self.conn = get_connection()

        class Person(ProxyTree):
            name = fields.StringField()
            age = fields.IntField()

        class ComplexPerson(ProxyTree):
            id = fields.StringPrimaryKey()
            name = fields.StringField()
            age = fields.IntField(default=30)
            height = fields.IntField()
            addressess = fields.ListField()

        Person.drop_tree()
        ComplexPerson.drop_tree()

        self.Person = Person
        self.ComplexPerson = ComplexPerson

    def tearDown(self):
        self.conn.flushdb()


    def test_repr(self):
        """Ensure that unicode representation works
        """
        class Article(ProxyTree):
            title = fields.StringField()

            def __unicode__(self):
                return self.title
        Article.drop_tree()
        doc = Article(title=u'привет мир')
        doc.save()
        dir_doc = Article.direct_tree(doc.id)
        self.assertEqual('<Article DirectTree: привет мир>', repr(dir_doc))

    def test_repr_none(self):
        """Ensure None values handled correctly
        """
        class Article(ProxyTree):
            title = fields.StringField()

            def __str__(self):
                return None

        Article.drop_tree()
        doc = Article(title=u'привет мир')
        doc.save()
        dir_doc = Article.direct_tree(doc.id)
        self.assertEqual('<Article DirectTree: None>', repr(dir_doc))

    def test_instantiating_with_illegal_subclass(self):
        """Ensure we can't instantiate classes with DirectTree as a base class
        """

        class DirectFoo(DirectTree):
            pass

        self.assertRaises(AttributeError, partial(DirectFoo, 'id'))

    def test_db_field_load(self):
        """Ensure we load data correctly
        """
        class Person(ProxyTree):
            name = fields.StringField(required=True)
            _rank = fields.StringField(required=False, db_field="rank")

            @property
            def rank(self):
                return self._rank or "Private"

        Person.drop_tree()
        id1 = Person(name="Jack", _rank="Corporal").save()
        id2 = Person(name="Fred").save()

        d1 = Person.direct_tree(id1)
        d2 = Person.direct_tree(id2)

        self.assertEqual(d1.rank, "Corporal")
        self.assertEqual(d2.rank, "Private")


    def test_custom_id_field(self):
        """Ensure we can read from Redis with custom id"""
        self.ComplexPerson.drop_tree()
        complex_person = self.ComplexPerson(
                id="cmplx", name="John",
                height=176, addressess=['Sunset Blvd 242'])
        complex_person.save()

        cperson_id = complex_person.id
        dperson = self.ComplexPerson.direct_tree(cperson_id)

        def set_id():
            dperson.id = "illegal assignment"

        self.assertRaises(AttributeError, set_id)

        self.assertRaises(exceptions.DoesNotExist,
             partial(self.ComplexPerson.direct_tree, "wrong_id"))


        self.assertEqual(dperson.id, cperson_id)
        self.assertEqual(dperson.pk, complex_person.pk)
        self.assertEqual(dperson.name, "John")
        self.assertEqual(dperson.age, 30)
        self.assertEqual(dperson.height, 176)
        self.assertEqual(dperson.addressess[0], 'Sunset Blvd 242')

    def test_save(self):
        # test with AutoPrimaryKey
        self.Person.drop_tree()
        person = self.Person(name="Buck", age=40)
        person.save()
        sperson = self.Person.direct_tree(person.id)
        self.assertEqual(sperson.id, person.id)
        self.assertEqual(sperson.name, "Buck")
        self.assertEqual(sperson.age, 40)

        self.ComplexPerson.drop_tree()
        complex_person = self.ComplexPerson(
                id="cmplx", name="John",
                height=176, addressess=['Sunset Blvd 242'])
        complex_person.save()
        cperson_id = complex_person.id
        dperson = self.ComplexPerson.direct_tree(cperson_id)

        dperson.name = "Yolo"
        dperson.addressess = ['23 Penn Ave']
        dperson.height += 4
        self.assertEqual(dperson.name, "Yolo")
        self.assertEqual(dperson.age, 30)
        self.assertEqual(dperson.height, 180)
        self.assertEqual(dperson.addressess[0], '23 Penn Ave')

        del dperson.name
        del dperson.age
        del dperson.height
        del dperson.addressess
        self.assertEqual(dperson.name, None)
        self.assertEqual(dperson.age, 30)
        self.assertEqual(dperson.height, 0)
        self.assertEqual(dperson.addressess, [])

        dperson.addressess.rappend("new address")
        self.assertEqual(dperson.addressess[0], "new address")

    def test_save_to_a_value_that_equates_to_false(self):
        self.ComplexPerson.drop_tree()
        complex_person = self.ComplexPerson(
                id="cmplx", name="John",
                height=176, addressess=['Sunset Blvd 242'])
        complex_person.save()

        dperson = self.ComplexPerson.direct_tree(complex_person.id)
        dperson.height = 0
        dperson.age = 0

        self.assertEqual(dperson.height, 0)
        self.assertEqual(dperson.age, 0)
        dperson.addressess = []
        self.assertEqual(dperson.addressess, [])

    def test_batch_update(self):
        self.ComplexPerson.drop_tree()
        complex_person = self.ComplexPerson(
                id="cmplx", name="John",
                height=176, addressess=['Sunset Blvd 242'])
        complex_person.save()

        dperson = self.ComplexPerson.direct_tree(complex_person.id)
        dperson.update(name="Joe", age=34, height=212, addressess=[])

        self.assertEqual(dperson.name, "Joe", msg=None)
        self.assertEqual(dperson.age, 34, msg=None)
        self.assertEqual(dperson.height, 212, msg=None)
        self.assertEqual(dperson.addressess, [], msg=None)

    def test_delete(self):
        """Ensure that tree may be deleted using the delete method.
        """
        conn = get_connection(self.Person._meta.db_alias)
        self.ComplexPerson.drop_tree()
        complex_person = self.ComplexPerson(
                id="cmplx", name="John",
                height=176, addressess=['Sunset Blvd 242'])
        complex_person.save()

        key = self.ComplexPerson._meta.tree_key_prefix + "*"
        count = len(tuple(conn.scan_iter(key)))
        self.assertEqual(count, 2) # <-- 1 key for a tree, 1 for a complex field
        complex_person.delete()
        count = len(tuple(conn.scan_iter(key)))
        self.assertEqual(count, 0)

    def test_save_list(self):
        """Ensure that a list field may be properly saved.
        """
        self.ComplexPerson.drop_tree()
        complex_person = self.ComplexPerson(
                id="cmplx", name="John",
                height=176)
        complex_person.addressess = adds = ['Sunset Blvd 242', 'Wash Heights 34']
        complex_person.save()

        conn = get_connection(self.ComplexPerson._meta.db_alias)
        pk = complex_person._active_operators['addressess']._field_pk
        db_adds = conn.lrange(pk, 0, -1)

        self.assertEqual(adds, [cPickle.loads(i) for i in db_adds])

    def test_null_field(self):
        class User(ProxyTree):
            name = fields.StringField()
            height = fields.IntField(default=184, null=True)
            str_fld = fields.StringField(null=True)
            int_fld = fields.IntField(null=True)
            flt_fld = fields.FloatField(null=True)

        User.drop_tree()
        u = User(name='user')
        uid = u.save()
        u_from_db = User.direct_tree(uid)
        u_from_db.height = None
        self.assertEquals(u_from_db.height, 0)
        self.assertEqual(u_from_db.str_fld, None)
        self.assertEqual(u_from_db.int_fld, 0)
        self.assertEqual(u_from_db.flt_fld, 0.0)
        User.drop_tree()

    def test_not_saved_eq(self):
        """Ensure we can compare documents not saved.
        """
        class Person(ProxyTree):
            pass

        p = Person()
        p1 = Person()
        self.assertNotEqual(p, p1)
        self.assertEqual(p, p)

    def test_values(self):
        data1 = {
            'name': "John",
            'age': 46,
            'height': 145,
            'addressess': ['Jeff. Ave 3221']
        }
        complex_person = self.ComplexPerson(**data1)
        complex_person.id = 'john'
        complex_person.save()

        dperson = self.ComplexPerson.direct_tree(complex_person.id)
        db_data1 = sorted(dperson.values().items())
        self.assertEqual(db_data1, sorted(data1.items()))

        data2 = {'name': "Joe",
                 'age': 32,
                 'height': 0,
                 'addressess': ['FooBar St 23']}

        dperson.update(**data2)
        db_data = sorted(dperson.values().items())
        expected_data = sorted(data2.items())
        self.assertEqual(db_data, expected_data)

        # test with selected field names
        field_names = ["name", "addressess"]
        expected = [("name", "Joe"), ("addressess", ["FooBar St 23"])]
        vals = dperson.values(*field_names)
        self.assertEqual(sorted(expected), sorted(vals.items()))

        # test with flat=True
        self.assertEqual(
                sorted(dperson.values(flat=True)),
                sorted(data2.values()))

        # test with flat=True and selected field names
        self.assertEqual(
            sorted(dperson.values(flat=True, *field_names)),
            sorted(zip(*expected)[1]))

    def test_validation(self):
        class Person(ProxyTree):
            domains = fields.ListField(fields.DomainField())
            age = fields.IntField()
            height = fields.IntField()

        person = Person(domains=["domain.com"], age=24, height=194)
        person.save()

        dperson = Person.direct_tree(person.id, validate=1)
        def wrong_domain():
            dperson.domains = ['sfs']
        self.assertRaises(exceptions.ValidationError, wrong_domain)

        def wrong_age():
            dperson.age = "dsf"
        self.assertRaises(exceptions.ValidationError, wrong_age)

        try:
            dperson.age = '3'
        except exceptions.ValidationError:
            self.fail()

        with dperson.switch_validation(False) as dper:
            try:
                dper.age = 'dfg'
                dper.domains = [243]
            except exceptions.ValidationError:
                self.fail()

if __name__ == '__main__':
    unittest.main()
