# -*- coding: utf-8 -*-
import sys
sys.path[0:0] = [""]

import unittest
from datetime import datetime

from redisengine import fields
from redisengine import exceptions
from redisengine.proxy.tree import ProxyTree
from redisengine.connection import connect, get_connection



__all__ = ("ValidatorErrorTest",)


class ValidatorErrorTest(unittest.TestCase):
    def setUp(self):
        connect(10)
        self.conn = get_connection()

    def tearDown(self):
        self.conn.flushdb()

    def test_to_dict(self):
        """Ensure a ValidationError handles error to_dict correctly.
        """
        error = exceptions.ValidationError('root')
        self.assertEqual(error.to_dict(), {})

        # 1st level error schema
        error.errors = {'1st': exceptions.ValidationError('bad 1st'), }
        self.assertTrue('1st' in error.to_dict())
        self.assertEqual(error.to_dict()['1st'], 'bad 1st')

        # 2nd level error schema
        error.errors = {'1st': exceptions.ValidationError('bad 1st', errors={
            '2nd': exceptions.ValidationError('bad 2nd'),
        })}
        self.assertTrue('1st' in error.to_dict())
        self.assertTrue(isinstance(error.to_dict()['1st'], dict))
        self.assertTrue('2nd' in error.to_dict()['1st'])
        self.assertEqual(error.to_dict()['1st']['2nd'], 'bad 2nd')

        # moar levels
        error.errors = {'1st': exceptions.ValidationError('bad 1st', errors={
            '2nd': exceptions.ValidationError('bad 2nd', errors={
                '3rd': exceptions.ValidationError('bad 3rd', errors={
                    '4th': exceptions.ValidationError('Inception'),
                }),
            }),
        })}
        self.assertTrue('1st' in error.to_dict())
        self.assertTrue('2nd' in error.to_dict()['1st'])
        self.assertTrue('3rd' in error.to_dict()['1st']['2nd'])
        self.assertTrue('4th' in error.to_dict()['1st']['2nd']['3rd'])
        self.assertEqual(error.to_dict()['1st']['2nd']['3rd']['4th'],
                         'Inception')

        self.assertEqual(error.message, "root(2nd.3rd.4th.Inception: ['1st'])")

    def test_tree_validation(self):
        class User(ProxyTree):
            id = fields.StringPrimaryKey()
            name = fields.StringField(required=True)

        try:
            User().validate()
        except exceptions.ValidationError, e:
            self.assertTrue("User:Unbound" in e.message)
            self.assertEqual(e.to_dict(), {
                'name': 'Field is required'})

        user = User(name="Funions")
        try:
            user.save()
        except exceptions.ValidationError, e:
            self.assertEqual('User-specified pk field cannot be None', e.message)

        user = User(id="RossC0", name="Ross")
        user.save()
        user.name = None
        try:
            user.save()
        except ValidationError, e:
            self.assertTrue("User:RossC0" in e.message)
            self.assertEqual(e.to_dict(), {
                'name': 'Field is required'})



if __name__ == '__main__':
    unittest.main()
