#!/usr/bin/env python

from setuptools import setup, find_packages, find_namespace_packages
from setuptools.command.install import install as install_command
import subprocess
import os
import re
import shutil

with open('requirements.txt') as f:
    required = []
    prog = re.compile("^[^-.]")
    for row in f.read().splitlines():
        if prog.match(row) is None:
            continue
        required.append(row)


class Install(install_command):
    """ Customized setuptools install command which uses pip. """

    def run(self):
        subprocess.call(['pip3', 'install', '-r', 'requirements.txt'])
        install_command.run(self)


class Locales(install_command):

    def run(self):
        languages = ["en"]
        domains = ["discovery", "rotation"]
        base_dir = os.getcwd()

        for domain in domains:
            pot_file = os.path.join(base_dir, "kdnrm", "locale", f"{domain}.pot")
            if os.path.exists(pot_file) is False:
                raise FileNotFoundError(f"Cannot find {pot_file}.")

            msgids = {}
            with open(pot_file, "r") as fh:
                for po_row in fh.readlines():
                    found = re.search(r'^msgid\s+"(.+)"$', po_row)
                    if found is not None:
                        msg = found.group(1)
                        msgids[msg] = True
                fh.close()

            # msgfmt -o kdnrm/locale/en/LC_MESSAGES/discovery.mo kdnrm/locale/en/LC_MESSAGES/discovery.po
            for language in languages:

                mo_file = os.path.join(base_dir, "kdnrm", "locale", language, "LC_MESSAGES", f"{domain}.mo")
                po_file = os.path.join(base_dir, "kdnrm", "locale", language, "LC_MESSAGES", f"{domain}.po")

                check = msgids.copy()
                with open(po_file, "r") as fh:
                    for po_row in fh.readlines():
                        found = re.search(r'^msgid\s+"(.+)"$', po_row)
                        if found is not None:
                            msg = found.group(1)
                            if msg not in check:
                                raise Exception(f"The file {po_file} has a msgid {msg} that does not exists in the POT "
                                                f"file {pot_file}")
                            check.pop(msg, None)
                    fh.close()
                    if len(check) > 0:
                        raise Exception(f"The file {po_file} is missing msgids: {', '.join(msg.keys())}")

                if os.path.exists(po_file) is False:
                    raise FileNotFoundError(f"Cannot find {po_file}.")

                cmd = ['msgfmt', '-o', mo_file, po_file]
                print("*", " ".join(cmd))
                subprocess.call(cmd)


class Wheel(install_command):

    user_options = install_command.user_options + [
        ('whlsrc=', None, "Build a wheel for the python code that is in this directory. Copy into 'libs' directory."),
        ('libdir=', None, "The directory to put the whl files."),
        ('reqfiles=', None, "List of requirement.txt to update."),
    ]

    def initialize_options(self):
        install_command.initialize_options(self)
        self.whlsrc = None
        self.libdir = None
        self.reqfiles = None

    def finalize_options(self):
        install_command.finalize_options(self)

    def run(self):
        global whlsrc
        global libdir
        global reqfiles
        whlsrc = self.whlsrc
        libdir = self.libdir
        reqfiles = self.reqfiles

        if isinstance(reqfiles, list) is False:
            reqfiles = [reqfiles]

        current_dir = os.getcwd()
        try:
            # Get existing fiels in the lib directory.
            os.chdir(self.libdir)
            sp = subprocess.run(["ls"], capture_output=True, text=True)
            existing_whls = []
            for file in sp.stdout.split("\n"):
                if file.endswith("whl") is True:
                    existing_whls.append(file)

            # Installed required modules and build a wheel
            os.chdir(whlsrc)
            subprocess.run(["pip3", "install", "-r", "requirements.txt"])
            subprocess.run(["python3", "setup.py", "clean"])
            subprocess.run(["rm", "-rf", "dist", "build"])
            subprocess.run(["python3", "setup.py", "bdist_wheel"])

            # Find the whl file in the dist folder.
            os.chdir(os.path.join(whlsrc, "dist"))
            sp = subprocess.run(["ls"], capture_output=True, text=True)
            wheel_file = None
            for file in sp.stdout.split("\n"):
                if file.endswith("whl") is True:
                    wheel_file = file
                    break
            if wheel_file is None:
                raise ValueError(f"Cannot find a whl file in the dist directory of the {whlsrc} project.")

            # Copy the whl to the lib directory
            print(f"copy {wheel_file} to {self.libdir}")
            subprocess.run(["cp", wheel_file, self.libdir])

            project_name = wheel_file[:wheel_file.index("-")]

            # Remove old versions of the wheel.
            os.chdir(self.libdir)
            for existing_whl in existing_whls:
                if existing_whl.startswith(project_name) is False:
                    continue
                if existing_whl == wheel_file:
                    continue
                os.unlink(existing_whl)

            for req in reqfiles:
                shutil.copy(req, f"{req}.bak")
                requirement_data = []
                with open(req, "r") as fh:
                    requirement_data = fh.readlines()
                    fh.close()

                pattern = re.compile(re.escape(project_name) + "-.*?.whl" )
                with open(req, "w") as fh:
                    for line in requirement_data:
                        line = re.sub(pattern, wheel_file, line)
                        fh.write(line)
                    fh.close()
                os.unlink(f"{req}.bak")

        finally:
            os.chdir(current_dir)


def get_version():

    # Get the absolute path to the directory containing this setup.py file
    here = os.path.abspath(os.path.dirname(__file__))
    version_file = os.path.join(here, 'kdnrm', '__version__.py')
    with open(version_file, 'r', encoding='utf-8') as fp:
        lines = fp.readlines()
    for line in lines:
        if line.startswith('__version__'):
            # Extract the version number
            delim = '"' if '"' in line else "'"
            return line.split(delim)[1]
    raise RuntimeError("Unable to find version string.")


setup(
    version=get_version(),
    name='kdnrm',
    description='Fake Keeper Discovery N Rotation Manager',
    url='https://github.com/Keeper-Security/discovery-and-rotation',
    packages=(find_packages() + find_namespace_packages(include=['kdnrm.*'])),
    package_data={"kdnrm.locale": ["*"]},
    install_requires=required,
    include_package_data=True,
    cmdclass={
        'install': Install,
        'locales': Locales,
        'wheel': Wheel
    },
    python_requires='>=3.10',
    entry_points={
        "console_scripts": [
            "kdnrm_test_tool=kdnrm.test_tool:main",
        ]
    }
)
