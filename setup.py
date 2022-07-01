#!/usr/bin/env python3
# Copyright (c) 2022 Shinyzenith <aakashsensharma@gmail.com>
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
# this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright
# notice, this list of conditions and the following disclaimer in the
# documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT
# NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY
# OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE,
# EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


import subprocess
import sys

from setuptools import setup
from setuptools.command.install import install


class CheckProtocolExistence(install):
    def protocol_check(self) -> bool:
        try:
            from pywayland.protocol.next_control_v1 import NextControlV1
            from pywayland.protocol.river_layout_v3 import RiverLayoutManagerV3
            return True
        except ModuleNotFoundError:
            return False

    def finalize_options(self):
        if not self.protocol_check():
            subprocess.run(
                [
                    "python3",
                    "-m",
                    "pywayland.scanner",
                    "-i",
                    "./protocols/river-layout-v3.xml",
                    "./protocols/next-control-v1.xml",
                    "/usr/share/wayland/wayland.xml",
                ]
            )
        install.finalize_options(self)


def get_cffi_modules():
    cffi_modules = []
    try:
        from cffi.error import PkgConfigError
        from cffi.pkgconfig import call
    except ImportError:
        # technically all ffi defined above wont be built
        print('CFFI package is missing')
    try:
        import wlroots.ffi_build
        cffi_modules.append(
            'libnext/libinput_ffi_build.py:libinput_ffi'
        )
    except ImportError:
        print(
            "Failed to find pywlroots. "
            "Wayland backend libinput configuration will be unavailable."
        )
        pass
    return cffi_modules


setup(
    cmdclass={'install': CheckProtocolExistence},
    cffi_modules=get_cffi_modules(),
    include_package_data=True,
)
