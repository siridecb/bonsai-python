from codecs import open
from setuptools import find_packages, setup
from os import path

# Get the long description from the README file
# And also convert to reST
try:
    from pypandoc import convert

    def read_md(f): return convert(f, 'rst')

except ImportError:
    print("warning: pypandoc module not found, "
          "could not convert Markdown to RST")

    def read_md(f): return open(f, 'r').read()

setup(
    name='bonsai-python',
    version='0.6.0',
    description='A library creating and training AIs with Bonsai BRAIN',
    long_description=read_md('README.md'),
    url='http://github.com/BonsaiAI/bonsai-python',
    author='Bonsai Engineering',
    author_email='opensource@bons.ai',
    license='BSD',
    classifiers=[
        'Development Status :: 4 - Beta',
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
        'protobuf>=3.0.0,<=3.1',
        'six>=1.10.0',
        'bonsai_config>=0.3.0',
    ],
    packages=find_packages()
    )
