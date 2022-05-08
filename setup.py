from setuptools import setup

# https://python-packaging.readthedocs.io/en/latest/minimal.html
setup(
    author="Radian LLC",
    author_email="contact+fstunes@radian.codes",
    description="Minimal command-line music library manager and media player.",
    license="MIT",
    install_requires=["mutagen"],
    name="fstunes",
    scripts=["scripts/fstunes"],
    url="https://github.com/radian-software/fstunes",
    version="0.0-dev",
)
