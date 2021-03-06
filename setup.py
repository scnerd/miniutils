from setuptools import setup, find_packages

setup(
    name='miniutils',
    version='1.0.3',
    packages=find_packages(),
    url='http://miniutils.readthedocs.io/en/latest/',
    license='MIT',
    author='scnerd',
    author_email='scnerd@gmail.com',
    description='Small Python utilities for adding concise functionality and usability to your code',
    long_description=open('README.rst').read(),
    install_requires=[
        'tqdm',
        'pycontracts',
        'coloredlogs',
    ],
    download_url='https://github.com/scnerd/miniutils',
    keywords=['miniutils', 'utilities', 'decorators', 'minimal'],
    python_requires='>=3',
)
