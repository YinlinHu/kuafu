
from setuptools import setup
from kuafu import __version__

def readme():
    with open('README.md') as f:
        return f.read()
    
setup(
      name='kuafu',
      version=__version__,
      description='Another PDF manager',
      long_description=readme(),
      long_description_content_type="text/markdown",
      keywords='Python PDFium',
      url='https://github.com/YinlinHu/kuafu',
      author='Yinlin Hu',
      author_email='huyinlin@gmail.com',
      license='GNU GPLv3',
      packages=['kuafu'],
      install_requires=['PyQt5', 'numpy', 'opencv-python-headless', 'pypdfium'], #external packages as dependencies
      classifiers=[
      'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
      'Operating System :: POSIX :: Linux',
      #'Operating System :: MacOS :: MacOS X',
      'Operating System :: Microsoft :: Windows',
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
