===========
RedisEngine
===========
:Info: RedisEngine is a MongoEngine-inspired lib for ORM-like manipulation of Redis-powered cache in Python.
:Repository: https://github.com/RedisEngine/redisengine
:Author: Kris Kavalieri (https://github.com/kriskavalieri)

About
=====
RedisEngine is intended to be an ORM-like Object-To-Redis-Type-Mapper written in Python.
This is a work in progress, as several things are pending completion, like: exhaustive tests,
CI, documentation and API reference.

**Given the above, any usage other than experimental is strongly discouraged for the time being.**

Future releases will include integration with Django's and MongoEngine's signal framework/module so that cache management can be automated
in a customizable fashion.


Motivation
==========
I found myself in an occasional need of cache validation which usually resulted in a more entropic (and WET) code to cope with.
It naturally occurred this would be the best course of action.



Installation
============
``pip install -U redisengine``.

Alternatively, download the `source <http://github.com/RedisEngine/redisengine>`_ and run
``python setup.py install``.



Dependencies
============
- redis>=2.10.5


Tests
=====
To run the test suite, ensure you are running a local instance of Redis on
the standard port, and run: ``python setup.py nosetests``.

Run selected tests with:

.. code-block:: shell

    $ python setup.py nosetests --tests tests/fields/test_fields.py:FieldTest.test_default_values_nothing_set -s

Community
=========
Yet to come

Contributing
============
Yet to come
