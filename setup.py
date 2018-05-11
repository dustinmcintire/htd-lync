# pylint: disable=invalid-name, exec-used
"""Setup HTD lync package."""
from __future__ import absolute_import
import sys
import os
from setuptools import setup, find_packages
# import subprocess
sys.path.insert(0, '.')

CURRENT_DIR = os.path.dirname(__file__)

# to deploy to pip, please use
# make pythonpack
# python setup.py register sdist upload
# and be sure to test it firstly using "python setup.py register sdist upload -r pypitest"
setup(name='lync',
      description='Lync API for HTD Lync6/12 and commands to provide support within home-assistant.io',
      version='0.1.0',
      long_description=open(os.path.join(CURRENT_DIR, 'README.md')).read(),
      install_requires=['requests'],
      maintainer='Dustin McIntire',
      maintainer_email='dustin.mcintire@gmail.com',
      zip_safe=False,
      packages=find_packages(),
      include_package_data=True,
      url='https://github.com/dustinmcintire/lync.git')
