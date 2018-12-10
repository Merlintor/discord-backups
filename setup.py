from setuptools import setup, find_packages


with open('README.md') as f:
    readme = f.read()

with open('LICENSE') as f:
    license = f.read()

setup(
    name='discord_backups',
    version='0.1.2',
    description='Create backups of your discord server',
    long_description=readme,
    author='Merlin Fuchs (Merlintor)',
    author_email='merlinfuchs2001@gmail.com',
    url='https://github.com/Merlintor/discord-backups',
    license=license,
    packages=find_packages(exclude=('tests', 'docs'))
)
