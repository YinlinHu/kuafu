
from setuptools import setup
from kuafu import __version__

from resources.compile_ui import compileUIFiles
compileUIFiles('./resources/')

setup(
      name='kuafu',
      version=__version__,
      description='PDF manager',
      keywords='poppler-qt5',
      url='',
      author='Yinlin Hu',
      author_email='huyinlin@gmail.com',
      license='GNU GPLv3',
      packages=['kuafu'],
      classifiers=[
      'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
      'Operating System :: POSIX :: Linux',
      'Programming Language :: Python :: 3',
      ],
      entry_points={
          'console_scripts': ['kuafu=kuafu.main:main'],
      },
      data_files=[
                 ('share/applications', ['resources/kuafu.desktop']),
                 ('share/icons', ['resources/icons/kuafu.svg']),
                 ('resources', ['resources/ui_main.py', 'resources/ui_library.py', 
                                'resources/ui_document.py', 'resources/resources_rc.py',
                                'resources/ui_annotation_item.py'])
      ],
      include_package_data=True,
      zip_safe=False
)
