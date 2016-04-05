from setuptools import setup, find_packages

CLS = [
    'Intended Audience :: Developers',
    'Topic :: Database',
    'Topic :: Software Development :: Libraries :: Python Modules',
]

setup(
  name='redisengine',
  packages=['redisengine'],
  version='0.1',
  license='MIT',
  include_package_data=True,
  description='A MongoEngine-inspired, Object-Type mapper for working with Redis',
  long_description=open('README.rst').read(),
  author='Kris Kavalieri',
  author_email='kris.kavalieri@gmail.com',
  download_url='https://github.com/RedisEngine/redisengine/tarball/master',
  classifiers=CLS,
  test_suite = 'nose.collector',
  install_requires=['redis>=2.10.5'],
  platforms=['any'],
  tests_require=['nose', 'rednose']
)
