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

from typing import Callable, Union

from pywayland.server import Listener, Signal

ColorType = Union[str, tuple[int, int, int], tuple[int, int, int, float]]


class Listeners:
    def add_listener(self, event: Signal, callback: Callable) -> None:
        """
        Add a listener to any event.
        """
        if not hasattr(self, "listeners"):
            self.listeners = []

        listener = Listener(callback)
        event.add(listener)
        self.listeners.append(listener)

    def destroy_listeners(self) -> None:
        """
        Destroy all assigned listeners.
        """
        for listener in reversed(self.listeners):
            listener.remove()


def rgb(x: ColorType) -> tuple[float, float, float, float]:
    """
    Parse
    """
    if isinstance(x, (tuple, list)):
        if len(x) == 4:
            alpha = x[-1]
        else:
            alpha = 1.0
        return "#%02x%02x%02x" % (x[0] / 255.0, x[1] / 255.0, x[2] / 255.0)
    elif isinstance(x, str):
        if x.startswith("#"):
            x = x[1:]
        if "." in x:
            x, alpha_str = x.split(".")
            alpha = float("0." + alpha_str)
        else:
            alpha = 1.0
        if len(x) not in (3, 6, 8):
            raise ValueError("RGB specifier must be 3, 6 or 8 characters long.")
        if len(x) == 3:
            vals = tuple(int(i, 16) * 17 for i in x)
        else:
            vals = tuple(int(i, 16) for i in (x[0:2], x[2:4], x[4:6]))
        if len(x) == 8:
            alpha = int(x[6:8], 16) / 255.0
            vals += (alpha,)
            return rgb(vals)
        raise ValueError("Invalid RGB specifier.")


def hex(x: ColorType) -> str:
    r, g, b, _ = rgb(x)
    return "#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255))
