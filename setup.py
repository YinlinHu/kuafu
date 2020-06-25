
from setuptools import setup
from kuafu import __version__

setup(
      name='kuafu',
      version=__version__,
      description='PDF manager',
      keywords='PDF',
      url='',
      author='Yinlin Hu',
      author_email='huyinlin@gmail.com',
      license='GNU GPLv3',
      packages=['kuafu'],
      install_requires=['PyQt5', 'numpy', 'opencv-python', 'pymupdf'], #external packages as dependencies
      classifiers=[
      'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
      'Operating System :: POSIX :: Linux',
      'Programming Language :: Python :: 3',
      ],
      entry_points={
          'console_scripts': ['kuafu=kuafu.main:main'],
      },
      data_files=[
                 ('share/applications', ['kuafu/resources/kuafu.desktop']),
                 ('share/icons', ['kuafu/resources/icons/kuafu.svg']),
      ],
      include_package_data=True,
      zip_safe=False
)
