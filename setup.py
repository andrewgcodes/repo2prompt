from setuptools import setup, find_packages

setup(
    name='Repo2Prompt',
    version='0.1.1',
    description='Github repo -> prompt string',
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        'requests>=2.20.0',
        'tqdm>=4.60.0',
        'aiohttp>=3.9.1',
    ],
)