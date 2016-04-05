#coding: utf-8
import unittest
from time import time

from redisengine import fields, exceptions
from redisengine.proxy.tree import ProxyTree
from redisengine.connection import connect, get_connection, register_connection

__all__ = ("TestProxyTree", )

class TestProxyTree(unittest.TestCase):
    def setUp(self):
        connect(10)
        self.db = get_connection()

        class Person(ProxyTree):
            name = fields.StringField()
            age = fields.IntField()

        class ComplexPerson(ProxyTree):
            name = fields.StringField()
            age = fields.IntField()
            addressess = fields.ListField()

        self.Person = Person
        self.ComplexPerson = ComplexPerson


    def tearDown(self):
        self.db.flushdb()


    def test_repr(self):
        """Ensure that unicode representation works
        """
        class Article(ProxyTree):
            title = fields.StringField()

            def __unicode__(self):
                return self.title

        doc = Article(title=u'привет мир')

        self.assertEqual('<Article ProxyTree: привет мир>', repr(doc))

    def test_repr_none(self):
        """Ensure None values handled correctly
        """
        class Article(ProxyTree):
            title = fields.StringField()

            def __str__(self):
                return None

        doc = Article(title=u'привет мир')
        self.assertEqual('<Article ProxyTree: None>', repr(doc))

    def test_disallowed_inheritance(self):
        """Ensure we can't subclass ProxyTree's subclasses
        """
        class Paper(ProxyTree):
            pass

        def create_inheriting_tree():
            class Article(Paper):
                pass
        self.assertRaises(ValueError, create_inheriting_tree)

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

        self.assertEqual(Person.proxy_tree(id1).rank, "Corporal")
        self.assertEqual(Person.proxy_tree(id2).rank, "Private")

    def test_custom_id_field(self):
        """Ensure that trees may be created with custom primary keys.
        """

        class User(ProxyTree):
            id = fields.StringPrimaryKey()
            name = fields.StringField()

        User.drop_tree()

        self.assertEqual(User._fields['id'].db_field, 'id')
        self.assertEqual(User._meta.pk_field_name, 'id')

        def create_tree_with_wrong_pk_field_name():
            class InvalidPKFieldNameUser(ProxyTree):
                username=fields.StringPrimaryKey()

        self.assertRaises(exceptions.InvalidTreeError,
                          create_tree_with_wrong_pk_field_name)

        def create_invalid_user():
            User(name='test').save()  # no primary key field
        self.assertRaises(exceptions.ValidationError, create_invalid_user)

        user = User(id='test', name='test user')
        user_id = user.save()

        # Raise ValidationError when trying to save with an explicitly set pk,
        # already associated with a tree
        pk_set_person = User(name='Joe', id=user_id)
        self.assertRaises(exceptions.ValidationError, pk_set_person.save)

        user_obj = User.proxy_tree(user_id)
        self.assertEqual(user_obj.id, 'test')
        self.assertEqual(user_obj.pk, 'user:test')

        User.drop_tree()

    def test_creation(self):
        """Ensure that tree may be created using keyword arguments.
        """
        person = self.Person(name="Test User", age=30)
        self.assertEqual(person.name, "Test User")
        self.assertEqual(person.age, 30)

    def test_reload(self):
        """Ensure that attributes may be reloaded.
        """
        a = self.Person(name="A", age=20)
        a_id = a.save()

        b = self.Person.proxy_tree(a_id)
        b.name = "B"
        b.age = 21
        b.save()

        self.assertEqual(a.name, "A")
        self.assertEqual(a.age, 20)

        a.reload('age')
        self.assertEqual(a.name, "A")
        self.assertEqual(a.age, 21)

        a.reload()
        self.assertEqual(a.name, "B")
        self.assertEqual(a.age, 21)

        a.reload()
        self.assertEqual(a.name, "B")
        self.assertEqual(a.age, 21)

    def test_tree_clean(self):
        from time import time
        class TestTree(ProxyTree):
            status = fields.StringField()
            pub_date = fields.IntField()

            def save(self, **k):
                super(TestTree, self).save(**k)

            def clean(self):
                if self.status == 'draft' and self.pub_date is not None:
                    msg = 'Draft entries may not have a publication date.'
                    raise exceptions.ValidationError(msg)
                # Set the pub_date for published items if not set.
                if self.status == 'published' and self.pub_date is None:
                    self.pub_date = int(time())

        TestTree.drop_tree()

        t = TestTree(status="draft", pub_date=int(time()))

        try:
            t.save()
        except exceptions.ValidationError, e:
            expect_msg = "Draft entries may not have a publication date."
            self.assertTrue(expect_msg in e.message)
            self.assertEqual(e.to_dict(), {'__all__': expect_msg})

        t = TestTree(status="published")
        t.save(clean=False)

        self.assertEqual(t.pub_date, None)

        t = TestTree(status="published")
        t.save(clean=True)

        self.assertEqual(type(t.pub_date), int)

    def test_save(self):
        """Ensure that a tree may be saved in the database.
        """
        # Create person object and save it to the database
        person = self.Person(name='Test User', age=30)
        pid = person.save()
        # Ensure that the object is in the database
        conn = get_connection(self.Person._meta.db_alias)
        person_obj = conn.hgetall(person.pk)
        self.assertEqual(person_obj['name'], 'Test User')
        self.assertEqual(person_obj['age'], '30') #<-- comparing to a string as Redis won't cast types
        # Test skipping validation on save

        class Recipient(ProxyTree):
            website = fields.DomainField(required=True)

        recipient = Recipient(website='root@localhost')
        self.assertRaises(exceptions.ValidationError, recipient.save)

        try:
            recipient.save(validate=False)
        except exceptions.ValidationError:
            self.fail()

    def test_save_to_a_value_that_equates_to_false(self):

        class Thing(ProxyTree):
            count = fields.IntField()

        Thing.drop_tree()
        user = Thing(count=1)
        user.save()
        user.count = 0
        user.save()
        user.reload()
        self.assertEqual(user.count, 0)

    def test_update(self):
        """Ensure that an existing document is updated instead of be
        overwritten."""
        conn = get_connection(self.Person._meta.db_alias)

        # Create person object and save it to the database
        person = self.Person(name='Test User', age=30)
        pid = person.save()

        # Create same person object, with same id, without age
        same_person = self.Person(name='Test')
        same_person.id = pid
        same_person.save(forced=True)

        same_person.reload()
        person.reload('age')

        # Confirm clash gets caught
        records_no = len(tuple(
                conn.scan_iter(
                    self.Person._meta.tree_key_prefix + "*")))
        self.assertEqual(records_no, 1)

         # reload
        person.reload()
        same_person.reload()

        # Confirm the same
        self.assertEqual(person, same_person)
        self.assertEqual(person.name, same_person.name)
        self.assertEqual(person.age, same_person.age)

        # Confirm the saved values
        self.assertEqual(person.name, 'Test')
        self.assertEqual(person.age, 30)

        # Test only updates included fields
        person = self.Person.proxy_tree(pid, only=["name"])
        person.name = 'User'
        person.save()

        person.reload()
        self.assertEqual(person.name, 'User')
        self.assertEqual(person.age, 30)

    def test_save_only_changed_fields(self):
        """Ensure save only sets / unsets changed fields
        """

        class Person(ProxyTree):
            name = fields.StringField()
            age = fields.IntField()
            active = fields.BooleanField(default=True)

        Person.drop_tree()

        # Create person object and save it to the database
        user = Person(name='Test Person', age=30, active=True)
        uid = user.save()
        user.reload()

        # Simulated Race condition
        same_person = Person.proxy_tree(uid)
        same_person.active = False

        user.age = 21
        user.save()

        same_person.name = 'Person'
        pid = same_person.save()

        person = Person.proxy_tree(pid)
        self.assertEqual(person.name, 'Person')
        self.assertEqual(person.age, 21)
        self.assertEqual(person.active, False)

    def test_delete(self):
        """Ensure that tree may be deleted using the delete method.
        """
        conn = get_connection(self.Person._meta.db_alias)
        person = self.Person(name="Test User", age=30)
        person.save()
        key = self.Person._meta.tree_key_prefix + "*"
        count = len(tuple(conn.scan_iter(key)))
        self.assertEqual(count, 1)
        person.delete()
        count = len(tuple(conn.scan_iter(key)))
        self.assertEqual(count, 0)

    def test_save_custom_id(self):
        """Ensure that a tree may be saved with a custom id.
        """
        # Create person object and save it to the database
        class Person(ProxyTree):
            name=fields.StringField()
            age=fields.IntField(default=30)
            id=fields.StringPrimaryKey()
        person = Person(name="Brian", id='loremporem')
        person.save()

        # Ensure that the object is in the database with the correct id
        conn = get_connection(self.Person._meta.db_alias)
        self.assertEqual(conn.exists(person.pk), 1)

    def test_save_list(self):
        """Ensure that a list field may be properly saved.
        """

        class BlogPost(ProxyTree):
            content = fields.StringField()
            tags = fields.ListField(fields.StringField())

        BlogPost.drop_tree()

        post = BlogPost(content='Went for a walk today...')
        post.tags = tags = ['fun', 'leisure']
        post.save()

        conn = get_connection(BlogPost._meta.db_alias)
        tags_pk = post._active_operators['tags']._field_pk
        db_tags = conn.lrange(tags_pk, 0, -1)
        self.assertEqual(db_tags, tags)

        BlogPost.drop_tree()

    def test_duplicate_db_fields_raise_invalid_document_error(self):
        """Ensure a InvalidTreeError is thrown if duplicate fields
        declare the same db_field"""

        def throw_invalid_document_error():
            class Foo(ProxyTree):
                name = fields.StringField()
                name2 = fields.StringField(db_field='name')
        self.assertRaises(exceptions.InvalidTreeError, throw_invalid_document_error)

    def test_throw_invalid_document_error(self):
        # test handles people trying to upsert
        def throw_invalid_document_error():
            class Blog(ProxyTree):
                validate = fields.StringField()

        self.assertRaises(exceptions.InvalidTreeError, throw_invalid_document_error)

    def test_can_save_false_values(self):
        """Ensures you can save False values on save"""
        class Doc(ProxyTree):
            foo = fields.StringField()
            archived = fields.BooleanField(default=False, required=True)

        Doc.drop_tree()
        d = Doc()
        d.save()
        d.archived = False
        d.save()

        self.assertEqual(d.archived, False)

    def test_db_alias_tests(self):
        """ DB Alias tests """
        # mongoenginetest - Is default connection alias from setUp()
        # Register Aliases
        register_connection('testdb-1', db=11)
        register_connection('testdb-2', db=12)

        class User(ProxyTree):
            name = fields.StringField()
            class Meta:
                db_alias = "testdb-1"

        class Book(ProxyTree):
            name = fields.StringField()
            class Meta:
                db_alias = "testdb-2"

        # Drops
        User.drop_tree()
        Book.drop_tree()

        # Create
        bob = User(name="Bob")
        bob_id = bob.save()
        hp = Book(name="Harry Potter")
        hp_id = hp.save()

        # Selects
        self.assertEqual(User.proxy_tree(bob_id), bob)
        self.assertEqual(Book.proxy_tree(hp_id), hp)

        # DB Alias
        testdb_1 = get_connection("testdb-1")
        testdb_2 = get_connection("testdb-2")
        self.assertEqual(bob._conn, testdb_1)
        self.assertEqual(hp._conn, testdb_2)

        testdb_1.flushdb()
        testdb_2.flushdb()


    def test_default_values(self):
        class Person(ProxyTree):
            created_on = fields.IntField(default=lambda: int(time()))
            name = fields.StringField()

        p = Person(name='alon')
        pid = p.save()
        orig_created_on = Person.proxy_tree(pid, only=['created_on']).created_on

        p2 = Person.proxy_tree(pid, only=['name'])
        p2.name = 'alon2'
        p2.save()
        p3 = Person.proxy_tree(pid, only=['created_on'])
        self.assertEquals(orig_created_on, p3.created_on)

        class Person(ProxyTree):
            created_on = fields.IntField(default=lambda: int(time()))
            name = fields.StringField()
            height = fields.IntField(default=189)

        p4 = Person.proxy_tree(pid)
        p4id = p4.save()
        self.assertEquals(p4.height, 189)

        # p4id
        conn = get_connection(Person._meta.db_alias)
        count = len(tuple(conn.scan_iter(p4.pk + "*")))
        self.assertEquals(count, 1)

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
        u_from_db = User.proxy_tree(uid)
        u_from_db.height = None
        u_from_db.save()
        self.assertEquals(u_from_db.height, None)
        self.assertEqual(u_from_db.str_fld, None)
        self.assertEqual(u_from_db.int_fld, None)
        self.assertEqual(u_from_db.flt_fld, None)
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
        class User(ProxyTree):
            id = fields.StringPrimaryKey()
            name = fields.StringField()

        User.drop_tree()
        u_data = {"name": "Foo Bar"}
        u = User(**u_data)
        u.id = "user-1"
        u.save()

        data = sorted(u.values().items())
        self.assertEqual(data, sorted(u_data.items()))

        data = {'name':"Joe",
                'age':323,
                'addressess': ["FooBar St 23"]}

        complex_person = self.ComplexPerson(**data)
        complex_person.save()
        complex_person = self.ComplexPerson.proxy_tree(complex_person.id)

        db_data = sorted(complex_person.values().items())

        expected_data = sorted(data.items())
        self.assertEqual(db_data, expected_data)

        # test with selected field names
        field_names = ["name", "addressess"]
        expected = [("name", "Joe"), ("addressess", ["FooBar St 23"])]
        vals = complex_person.values(*field_names)
        self.assertEqual(sorted(expected), sorted(vals.items()))

        # test with flat=True
        self.assertEqual(
                sorted(complex_person.values(flat=True)),
                sorted(data.values()))

        # test with flat=True and selected field names
        self.assertEqual(
            sorted(complex_person.values(flat=True, *field_names)),
            sorted(zip(*expected)[1]))


if __name__ == '__main__':
    unittest.main()
