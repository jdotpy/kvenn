from setuptools import setup

with open("README.md", "r") as f:
    long_description = f.read()

setup(
    name = 'kvenn',
    entry_points={
      'console_scripts': ['kvenn=kvenn.core:cli'],
    },
    version = '2.0.0',
    description = 'CLI tool for doing set operations (e.g. intersection, difference, union) on lines of input',
    long_description=long_description,
    long_description_content_type="text/markdown",
    author = 'KJ',
    author_email = 'jdotpy@users.noreply.github.com',
    url = 'https://github.com/jdotpy/kvenn',
    download_url = 'https://github.com/jdotpy/kvenn/tarball/master',
    keywords = ['tools'],
    classifiers = [],
    extras_require={
        'dev': ['pytest'],
    },
)
