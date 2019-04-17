"""A setuptools based setup module.
See:
https://packaging.python.org/en/latest/distributing.html
https://github.com/pypa/sampleproject
"""

import os

from codecs import open
from os import path

from setuptools import setup

root = path.dirname(path.abspath(__file__))

with open(path.join(root, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='plz-cli',
    version='0.1.' + os.environ.get('BUILD_TIMESTAMP', '0'),
    description='Send jobs to the Plz server',
    long_description=long_description,
    url='https://github.com/prodo-ai/plz',
    author='Prodo Tech Ltd.',
    author_email='hello@prodo.ai',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Build Tools',
        'License :: Other/Proprietary License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
    ],
    package_dir={
        '': 'src',
        'plz.controller.api': '../services/controller/src/plz/controller/api'
    },
    packages=['plz.cli', 'plz.controller.api'],
    python_requires='>= 3.6',
    install_requires=[
        'docker >= 3.3.0',
        'glob2 >= 0.6',
        'paramiko >= 2.4.1',
        'prettytable >= 0.7.2',
        'python-dateutil >= 2.7.3',
        'requests >= 2.20.0',
        'urllib3 >= 1.23',
    ],
    extras_require={
        'test': [
            'flake8==3.5.0',
            'nose==1.3.7',
            'flask >= 1.0.2', ], },
    entry_points={
        'console_scripts': ['plz=plz.cli.main:main'], },
    project_urls={
        'Bug Reports': 'https://github.com/prodo-ai/plz/issues', },
)
