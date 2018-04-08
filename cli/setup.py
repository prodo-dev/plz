"""A setuptools based setup module.
See:
https://packaging.python.org/en/latest/distributing.html
https://github.com/pypa/sampleproject
"""

from codecs import open
from os import path

from setuptools import setup

root = path.dirname(path.abspath(__file__))

with open(path.join(root, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='plz-cli',
    version='0.1.0',
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
    package_dir={'': 'src'},
    packages=['plz.cli'],
    python_requires='>= 3.6',
    # TODO: generate from Pipfile
    install_requires=[
        'docker >= 3.1.1',
        'prettytable >= 0.7.2',
        'requests >= 2.18.4',
    ],
    extras_require={
        'test': [
            'flake8==3.5.0',
            'nose==1.3.7',
        ],
    },
    entry_points={
        'console_scripts': [
            'plz=plz.cli.main:main',
        ],
    },
    project_urls={
        'Bug Reports': 'https://github.com/prodo-ai/plz/issues',
    },
)
