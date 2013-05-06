# This file is a part of the Panda plugin for MediaCore CE,
# Copyright 2011-2013 MediaCore Inc., Felix Schwarz and other contributors.
# For the exact contribution history, see the git revision log.
# The source code contained in this file is licensed under the GPLv3 or
# (at your option) any later version.
# See LICENSE.txt in the main project directory, for more information.

from setuptools import setup, find_packages

setup(
    name = 'MediaCore-Panda',
    description = 'A MediaCore CE plugin for using the Panda online transcoding service with Amazon S3.',
    version = '0.10',
    
    author = 'Anthony Theocharis',
    author_email = 'anthony@simplestation.com',
    license='GPL v3 or later', # see LICENSE.txt
    
    packages=find_packages(),
    namespace_packages = ['mediacoreext'],
    include_package_data=True,    
    zip_safe = False,
    
    install_requires = [
        'MediaCore >= 0.10dev',
        'simplejson',
        'panda == 0.1.2',
    ],
    entry_points = '''
        [mediacore.plugin]
        panda = mediacoreext.simplestation.panda.mediacore_plugin
    ''',
    message_extractors = {'mediacoreext/simplestation/panda': [
        ('**.py', 'python', None),
        ('templates/**.html', 'genshi', {'template_class': 'genshi.template.markup:MarkupTemplate'}),
        ('public/**', 'ignore', None),
        ('tests/**', 'ignore', None),
    ]},
)
