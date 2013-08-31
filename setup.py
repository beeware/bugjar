#/usr/bin/env python
import sys

from setuptools import setup
from bugjar import VERSION

try:
    readme = open('README.rst')
    long_description = str(readme.read())
finally:
    readme.close()

required_pkgs = [
    'Pygments>=1.5',
    'tkreadonly',
]
if sys.version_info < (2, 7):
    required_pkgs.append('argparse')

setup(
    name='bugjar',
    version=VERSION,
    description='A graphical Python debugger.',
    long_description=long_description,
    author='Russell Keith-Magee',
    author_email='russell@keith-magee.com',
    url='http://pybee.org/bugjar',
    packages=[
        'bugjar',
    ],
    install_requires=required_pkgs,
    scripts=[],
    entry_points={
        'console_scripts': [
            'bugjar = bugjar.main:local',
            'bugjar-jar = bugjar.main:jar',
            'bugjar-net = bugjar.main:net',
        ]
    },
    license='New BSD',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2',
        'Topic :: Software Development',
        'Topic :: Utilities',
    ],
    test_suite='tests'
)
