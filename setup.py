# setup.py
from setuptools import setup, find_packages

setup(
    name='tui',
    version='0.1.0',
    author='Fraser M. Callaghan',
    author_email='callaghan.fm@gmail.com',
    description='Basic viewer to load 3D/4D image data with basic markup capabilities.',
    long_description=open('README.md').read(),  # Ensure you have a README.md file
    long_description_content_type='text/markdown',
    # url='https://github.com/fraser29/tui',  # Replace with your repo URL
    packages=find_packages(),
    install_requires=[
        'vtk>=9.3',
        'PyQT5>=5.15.10',

        'spydcmtk', 
        'ngawari',  
    ],
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: GNU GPL V3', 
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.6',  
)
