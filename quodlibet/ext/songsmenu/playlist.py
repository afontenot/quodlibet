# Copyright 2009 Christoph Reiter
#      2014-2020 Nick Boultbee
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

# The Unofficial M3U and PLS Specification (Winamp):
# http://forums.winamp.com/showthread.php?threadid=65772

import os

from gi.repository import Gtk
from os.path import relpath

from quodlibet.plugins.playlist import PlaylistPlugin
from quodlibet import _
from quodlibet import util, qltk
from quodlibet.util.path import get_home_dir
from quodlibet.qltk.msg import ConfirmFileReplace
from quodlibet.qltk import Icons
from quodlibet.plugins.songsmenu import SongsMenuPlugin


lastfolder = get_home_dir()


class PlaylistExport(PlaylistPlugin, SongsMenuPlugin):
    PLUGIN_ID = 'Playlist Export'
    PLUGIN_NAME = _('Export as M3U / PLS Playlist File')
    PLUGIN_DESC = _('Exports songs to an M3U or PLS playlist.')
    PLUGIN_ICON = Icons.DOCUMENT_SAVE_AS
    REQUIRES_ACTION = True

    lastfolder = None

    def plugin_single_playlist(self, playlist):
        return self.__save_playlist(playlist.songs, playlist.name)

    def plugin_songs(self, songs):
        self.__save_playlist(songs)

    def __save_playlist(self, songs, name=None):
        dialog = Gtk.FileChooserDialog(self.PLUGIN_NAME,
            None,
            Gtk.FileChooserAction.SAVE)
        dialog.set_show_hidden(False)
        dialog.set_create_folders(True)
        dialog.add_button(_("_Cancel"), Gtk.ResponseType.CANCEL)
        dialog.add_button(_("_Save"), Gtk.ResponseType.OK)
        dialog.set_default_response(Gtk.ResponseType.OK)
        if name:
            dialog.set_current_name(name)

        ffilter = Gtk.FileFilter()
        ffilter.set_name("m3u")
        ffilter.add_mime_type("audio/x-mpegurl")
        ffilter.add_pattern("*.m3u")
        dialog.add_filter(ffilter)

        ffilter = Gtk.FileFilter()
        ffilter.set_name("pls")
        ffilter.add_mime_type("audio/x-scpls")
        ffilter.add_pattern("*.pls")
        dialog.add_filter(ffilter)

        dialog.set_current_folder(lastfolder)

        diag_cont = dialog.get_child()
        hbox_path = Gtk.HBox()
        combo_path = Gtk.ComboBoxText()
        hbox_path.pack_end(combo_path, False, False, 6)
        diag_cont.pack_start(hbox_path, False, False, 0)
        diag_cont.show_all()

        for option_text in [_("Use relative paths"), _("Use absolute paths")]:
            combo_path.append_text(option_text)
        combo_path.set_active(0)

        response = dialog.run()

        if response == Gtk.ResponseType.OK:
            file_path = dialog.get_filename()
            dir_path = os.path.dirname(file_path)

            file_format = dialog.get_filter().get_name()
            extension = "." + file_format
            if not file_path.endswith(extension):
                file_path += extension

            if os.path.exists(file_path):
                resp = ConfirmFileReplace(self.plugin_window, file_path).run()
                if resp != ConfirmFileReplace.RESPONSE_REPLACE:
                    return

            relative = combo_path.get_active() == 0

            files = self.__get_files(songs, dir_path, relative)
            if file_format == "m3u":
                self.__m3u_export(file_path, files)
            elif file_format == "pls":
                self.__pls_export(file_path, files)

            self.lastfolder = dir_path

        dialog.destroy()

    def __get_files(self, songs, dir_path, relative=False):
        files = []
        for song in songs:
            f = {}
            if "~uri" in song:
                f['path'] = song('~filename')
                f['title'] = song("title")
                f['length'] = -1
            else:
                path = song('~filename')
                if relative:
                    path = relpath(path, dir_path)
                f['path'] = path
                f['title'] = "%s - %s" % (
                    song('~people').replace("\n", ", "),
                    song('~title~version'))
                f['length'] = song('~#length')
            files.append(f)
        return files

    def __file_error(self, file_path):
        qltk.ErrorMessage(
            None,
            _("Unable to export playlist"),
            _("Writing to <b>%s</b> failed.") % util.escape(file_path)).run()

    def __m3u_export(self, file_path, files):
        try:
            fhandler = open(file_path, "wb")
        except IOError:
            self.__file_error(file_path)
        else:
            text = "#EXTM3U\n"

            for f in files:
                text += "#EXTINF:%d,%s\n" % (f['length'], f['title'])
                text += f['path'] + "\n"

            fhandler.write(text.encode("utf-8"))
            fhandler.close()

    def __pls_export(self, file_path, files):
        try:
            fhandler = open(file_path, "wb")
        except IOError:
            self.__file_error(file_path)
        else:
            text = "[playlist]\n"

            for num, f in enumerate(files):
                num += 1
                text += "File%d=%s\n" % (num, f['path'])
                text += "Title%d=%s\n" % (num, f['title'])
                text += "Length%d=%s\n" % (num, f['length'])

            text += "NumberOfEntries=%d\n" % len(files)
            text += "Version=2\n"

            fhandler.write(text.encode("utf-8"))
            fhandler.close()
