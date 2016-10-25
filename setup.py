from codecs import open
from setuptools import find_packages, setup
from os import path

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='bonsai-python',
    version='0.5.0',
    description='A library creating and training AIs with Bonsai BRAIN',
    long_description=long_description,
    url='http://github.com/BonsaiAI/bonsai-python',
    author='Bonsai Engineering',
    author_email='opensource@bons.ai',
    license='BSD',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Topic :: Scientific/Engineering :: Artificial Intelligence',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Natural Language :: English'
    ],
    keywords='bonsai',
    install_requires=[
        'tornado>=4.2.2',
        'protobuf>=3.0.0,<4',
        'six>=1.10.0',
        'bonsai_config>=0.3.0',
    ],
    packages=find_packages()
    )
