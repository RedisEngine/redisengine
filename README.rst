===========
RedisEngine
===========
:Info: RedisEngine is a MongoEngine-inspired lib for ORM-like manipulation of Redis-powered cache in Python.
:Repository: https://github.com/RedisEngine/redisengine
:Author: Kris Kavalieri (https://github.com/kriskavalieri)

About
=====
RedisEngine is **intended** to be a Python Object-Type Mapper for working with Redis.
This is a work in progress, as several things are pending completion like exhaustive tests,
CI, documentation and API ref.


**Given the above, any usage other than experimental is strongly discouraged for the time being.**

Installation
============
``pip install -U redisengine``.
`GitHub <http://github.com/RedisEngine/redisengine>`_ and run ``python setup.py install``.

Alternatively, download the `source <http://github.com/RedisEngine/redisengine>`_ and run ``python setup.py install``.



Dependencies
============
- redis>=2.10.5


Tests
=====
To run the test suite, ensure you are running a local instance of MongoDB on
the standard port, and run: ``python setup.py nosetests``.

If you wish to run one single or selected tests, use the nosetest convention. It will find the folder,
eventually the file, go to the TestClass specified after the colon and eventually right to the single test.
Also use the -s argument if you want to print out whatever or access pdb while testing.

.. code-block:: shell

    $ python setup.py nosetests --tests tests/fields/test_fields.py:FieldTest.test_default_values_nothing_set -s

Community
=========
Yet to come

Contributing
============
Yet to come
