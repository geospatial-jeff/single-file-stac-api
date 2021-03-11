"""aiocogeo packaging"""
from setuptools import find_packages, setup

with open("README.md") as f:
    desc = f.read()

extra_reqs = {
    "dev": ["pytest", "pytest-cov", "pre-commit", "tox"],
}

install_requires = ["arturo-stac-api", "pygeos"]

setup(
    name="single-file-stac-api",
    description="API for Single File STACs",
    long_description=desc,
    long_description_content_type="text/markdown",
    version="0.1.0",
    author=u"Jeff Albrecht",
    author_email="geospatialjeff@gmail.com",
    url="https://github.com/geospatial-jeff/single-file-stac-api",
    license="mit",
    python_requires=">=3.8",
    classifiers=[
        "Intended Audience :: Developers",
        "Intended Audience :: Information Technology",
        "Intended Audience :: Science/Research",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "License :: OSI Approved :: MIT License",
    ],
    keywords="STAC",
    packages=find_packages(exclude=["tests"]),
    include_package_data=True,
    install_requires=install_requires,
    extras_require=extra_reqs,
    tests_require=extra_reqs["dev"],
    entry_points={"console_scripts": ["sfs-api=single_file_stac_api.scripts.cli:api"]},
)
