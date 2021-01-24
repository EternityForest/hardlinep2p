import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="hardline",
    version="0.0.13",
    author="Daniel Dunn",
    author_email="dannydunn@eternityforest.com",
    description="HardlineP2P is a way to make web services securely acessible to the world, without any manual DNS or certificate setup",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/EternityForest/hardlinep2p",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: OS Independent"
    ],
    python_requires='>=3.6',
    install_requires=[
          'pyOpenSSL','pynacl','requests','lxml','six','python-dateutil','kivy','kivymd'
      ],
    scripts=['bin/hardlined', 'bin/hardline-gui']
)


#To push to pypi
#sudo python3 setup.py sdist bdist_wheel
#python3 -m twine upload dist/* 
