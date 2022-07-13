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
import logging
from typing import Any, Generic, TypeVar, Union

import pywayland
from pywayland.server import Listener
from wlroots import PtrHasData, ffi
from wlroots.util.edges import Edges
from wlroots.wlr_types import SceneNode, foreign_toplevel_management_v1
from wlroots.wlr_types.surface import SubSurface
from wlroots.wlr_types.xdg_shell import (
    XdgPopup,
    XdgSurface,
    XdgTopLevelSetFullscreenEvent,
)

from libnext import util
from libnext.util import Listeners

EDGES_TILED = Edges.TOP | Edges.BOTTOM | Edges.LEFT | Edges.RIGHT
EDGES_FLOAT = Edges.NONE

Surface = TypeVar("Surface", bound=PtrHasData)
log = logging.getLogger("Next: Window")


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
        self.mapped: bool = False
        self.scene_node: SceneNode

        self.x = 0
        self.y = 0
        self.width: int = 0
        self.float_width: int = 0
        self.height: int = 0
        self.float_height: int = 0
        self.opacity: float = 1.0

        self.borderwidth: int = 0
        self.bordercolor: list[ffi.CData] = [rgb((0, 0, 0, 1))]

        self.name: str = "<No Name>"
        self.wm_class: str | None = None

        surface.data = (
            self.ftm_handle
        ) = self.core.foreign_toplevel_managerv1.create_handle()

    def destroy(self) -> None:
        self.destroy_listeners()
        self.ftm_handle.destroy()

    def window_at(
        self, layout_x: int, layout_y: int
    ) -> tuple[Surface | None, float, float]:
        view_x = layout_x - self.x
        view_y = layout_y - self.y
        return self.surface.surface_at(view_x, view_y)

    def set_border(self, color: util.ColorType | None, width: int) -> None:
        # NOTE: Does this need anything else? Check qtile.
        if color:
            if isinstance(color, list):
                self.bordercolor = [rgb(c) for c in color]
            else:
                self.bordercolor = [rgb(color)]
        self.borderwidth = width

    def _on_destroy(self, _listener: Listener, _data: Any) -> None:
        """
        Window destroy callback.
        """
        log.debug("Signal: window_destroy_event")
        if self.mapped:
            log.warn("Window destroy signal sent before unmap event.")
            self.mapped = False
            self.core.mapped_windows.remove(self)
            # Focus on the next window.
            if len(self.core.mapped_windows) >= 1:
                self.core.focus_window(self.core.mapped_windows[-1])

        if self in self.core.pending_windows:
            self.core.pending_windows.remove(self)

        self.destroy()


WindowType = Union[Window]


class XdgWindow(Window[XdgSurface]):
    """
    Wayland client connecting over xdg_shell
    """

    def __init__(self, core, surface: XdgSurface):
        super().__init__(core, surface)

        self.wm_class = surface.toplevel.app_id
        self.popups: list[XdgPopupWindow] = []
        self.subsurfaces: list[SubSurface] = []
        self.scene_node = SceneNode.xdg_surface_create(self.core.scene.node, surface)

        self.fullscreen: bool = False
        # NOTE: Do we really need this?
        self.maximized: bool = False

        # TODO: Finish this.
        self.add_listener(self.surface.destroy_event, self._on_destroy)
        self.add_listener(self.surface.map_event, self._on_map)
        self.add_listener(self.surface.new_popup_event, self._on_new_popup)
        self.add_listener(self.surface.unmap_event, self._on_unmap)

    def _on_map(self, _listener: Listener, _data: Any) -> None:
        log.debug("Signal: wlr_xdg_surface_map_event")
        if self in self.core.pending_windows:
            log.debug("Managing a new top-level window")
            self.core.pending_windows.remove(self)
            self.mapped = True

            geometry = self.surface.get_geometry()
            self.width = self.float_width = geometry.width
            self.height = self.float_height = geometry.height

            self.surface.set_tiled(EDGES_TILED)

            if self.surface.toplevel.title:
                self.name = self.surface.toplevel.title
                self.ftm_handle.set_title(self.name)

            if self.wm_class:
                self.ftm_handle.set_app_id(self.wm_class or "")

            # TODO: Toplevel listeners go here.
            self.add_listener(
                self.surface.toplevel.request_fullscreen_event,
                self._on_request_fullscreen,
            )
            self.add_listener(self.surface.toplevel.set_title_event, self._on_set_title)
            self.add_listener(
                self.surface.toplevel.set_app_id_event, self._on_set_app_id
            )
            # foreign_toplevel_management_v1 callbacks.
            self.add_listener(
                self.ftm_handle.request_maximize_event,
                self._on_foreign_request_maximize,
            )
            self.add_listener(
                self.ftm_handle.request_fullscreen_event,
                self._on_foreign_request_fullscreen,
            )

            self.core.mapped_windows.append(self)
            self.core.focus_window(self)
            # TODO: Remove this before first release candidate.
            # This is only here for testing.
            self.place(0, 0, 1920, 1080, 0, None, True, None, False)

    def get_pid(self) -> int:
        pid = pywayland.ffi.new("pid_t *")
        pywayland.lib.wl_client_get_credentials(
            self.surface._ptr.client.client, pid, ffi.NULL, ffi.NULL
        )
        return pid[0]

    def kill(self) -> None:
        self.surface.send_close()

    def place(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        borderwidth: int,
        bordercolor: util.ColorType | None,
        above: bool = False,
        margin: int | list[int] | None = None,
        respect_hints: bool = False,
    ) -> None:
        if margin is not None:
            if isinstance(margin, int):
                margin = [margin] * 4
            x += margin[3]
            y += margin[0]
            width -= margin[1] + margin[3]
            height -= margin[0] + margin[2]
        # TODO: This is incomplete. Finish this.

        self.x = x
        self.y = y
        self.width = int(width)
        self.height = int(height)
        self.surface.set_size(self.width, self.height)
        self.scene_node.set_position(self.x, self.y)
        self.set_border(bordercolor, borderwidth)

        if above:
            self.core.focus_window(self)

    def _on_foreign_request_maximize(
        self,
        _listener: Listener,
        event: foreign_toplevel_management_v1.ForeignToplevelHandleV1MaximizedEvent,
    ) -> None:
        log.debug("Signal: wlr_foreign_toplevel_management_request_maximize")
        self.maximized = event.maximized

    def _on_foreign_request_fullscreen(
        self,
        _listener: Listener,
        event: foreign_toplevel_management_v1.ForeignToplevelHandleV1FullscreenEvent,
    ) -> None:
        log.debug("Signal: wlr_foreign_toplevel_management_request_fullscreen")
        self.borderwidth = 0
        self.fullscreen = event.fullscreen

    def _on_request_fullscreen(
        self, _listener: Listener, event: XdgTopLevelSetFullscreenEvent
    ) -> None:
        log.debug("Signal: wlr_xdg_surface_toplevel_request_fullscreen")
        self.borderwidth = 0
        self.fullscreen = event.fullscreen

    def _on_set_title(self, _listener: Listener, _data: Any) -> None:
        log.debug("Signal: wlr_xdg_surface_toplevel_set_title")
        title = self.surface.toplevel.title

        if title and title != self.name:
            self.name = title
            self.ftm_handle.set_title(self.name)

    def _on_set_app_id(self, _listener: Listener, _data: Any) -> None:
        log.debug("Signal: wlr_xdg_surface_toplevel_set_app_id")
        self.wm_class = self.surface.toplevel.app_id

        if (
            self.surface.toplevel.app_id
            and self.surface.toplevel.app_id != self.wm_class  # noqa: W503
        ):
            self.ftm_handle.set_app_id(self.wm_class or "")

    def _on_new_popup(self, _listener: Listener, xdg_popup: XdgPopup) -> None:
        log.debug("Signal: wlr_xdg_surface_new_popup_event")
        self.popups.append(XdgPopupWindow(self, xdg_popup))

    def _on_unmap(self, _listener: Listener, _data: Any) -> None:
        log.debug("Signal: wlr_xdg_surface_unmap_event")
        self.mapped = False
        self.core.mapped_windows.remove(self)

        # Focus on the next window.
        if len(self.core.mapped_windows) >= 1:
            self.core.focus_window(self.core.mapped_windows[-1])


class XdgPopupWindow(Listeners):
    # parent: Any because it can be a nested popup too aka XdgPopupWindow.
    def __init__(self, parent: XdgWindow | Any, xdg_popup: XdgPopup):
        self.scene_node = SceneNode.xdg_surface_create(
            parent.scene_node, parent.surface
        )
        # TODO: Finish this.
