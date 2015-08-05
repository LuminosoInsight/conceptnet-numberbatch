from setuptools import setup

setup(
    name = 'wide_learning',
    version = '0.1',
    install_requires=[
        'pandas', 'conceptnet==5.4a1', 'ftfy>=4.0', 'numpy', 'scikit-learn', 'wordfreq >= 1.0b4'
    ]
)
