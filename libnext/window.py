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

import functools
from typing import Generic, TypeVar, Union

from wlroots import PtrHasData, ffi
from wlroots.util.edges import Edges
from wlroots.wlr_types import SceneNode
from wlroots.wlr_types.xdg_shell import XdgSurface

from libnext import util
from libnext.util import Listeners

EDGES_TILED = Edges.TOP | Edges.BOTTOM | Edges.LEFT | Edges.RIGHT
EDGES_FLOAT = Edges.NONE

Surface = TypeVar("S", bound=PtrHasData)


@functools.lru_cache()
def rgb(color: util.ColorType) -> ffi.CData:
    if isinstance(color, ffi.CData):
        return color
    return ffi.new("float[4]", util.rgb(color))


class Window(Generic[Surface], Listeners):
    """
    Generic class for windows.
    """
    def __init__(self, core, surface: Surface):
        self.core = core
        self.surface = surface
        self.scene_node = SceneNode.xdg_surface_create(self.core.scene, surface)
        self.mapped: bool = False

        self.x = 0
        self.y = 0
        self.width: int = 0
        self.height: int = 0
        self.opacity: float = 1.0

        self.borderwidth: int = 0
        self.bordercolor: list[ffi.CData] = [rgb((0, 0, 0, 1))]

        self.name: str = "<No Name>"
        self.wm_class: str | None = None

    def destroy(self) -> None:
        self.destroy_listeners()

    @property
    def wid(self) -> int:
        """
        Return the window ID.
        """
        return self._wid

    @property
    def width(self) -> int:
        """
        Return the window width.
        """
        return self._width

    @width.setter
    def width(self, width: int) -> None:
        """
        Set the window width.
        """
        self._width = width

    @property
    def height(self) -> int:
        """
        Return the window height.
        """
        return self._height

    @height.setter
    def height(self, height: int) -> None:
        """
        Set the window height.
        """
        self._height = height


WindowType = Union[Window]


class XdgWindow(Window[XdgSurface]):
    """
    Wayland client connecting over xdg_shell
    """
    def __init__(self, core, surface: XdgSurface):
        Window.__init__(self, core, surface)
        self.wm_class = surface.toplevel.app_id
