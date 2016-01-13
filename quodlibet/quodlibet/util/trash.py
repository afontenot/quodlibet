# -*- coding: utf-8 -*-
# Copyright 2011 Christoph Reiter
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation

import os
import stat
import sys
import errno
import urllib
import time
import shutil

from os.path import join, islink, abspath, dirname
from os.path import isdir, basename, exists, splitext

from quodlibet import config
from quodlibet.util.path import find_mount_point, xdg_get_data_home


class TrashError(EnvironmentError):
    pass


def is_sticky(path):
    return bool(os.stat(path).st_mode & stat.S_ISVTX)


def _get_fd_trash_dirs(path):
    """Returns verified trash folders for the given path.

    Returns (rootdir, filesdir, infodir), or raises a TrashError if a
    valid trash folder structure could not be found. The returned trash
    folders are not guaranteed to be on the same volume as the original
    path: a fallback may be returned instead.

    Returned paths are absolute. This method may create partial or
    complete trash directory structures as part of its search.
    """

    path = abspath(path)
    mount = find_mount_point(path)
    xdg_data_home = xdg_get_data_home()
    xdg_home_mount = find_mount_point(xdg_data_home)
    trash_home = join(xdg_data_home, "Trash")
    # Build a list of trash roots to try.
    trash_roots = []
    if mount != xdg_home_mount:
        root = join(mount, ".Trash")
        uid = str(os.getuid())
        if isdir(root) and not islink(root) and is_sticky(root):
            trash_roots.append(join(root, uid))
        else:
            trash_roots.append(join(mount, ".Trash-" + uid))
    trash_roots.append(trash_home)
    trash_roots = [abspath(r) for r in trash_roots]
    # Try and verify each potential trash path, and create its
    # required structure if needed.
    for trash_root in trash_roots:
        if path.startswith(join(trash_root, "")) or path == trash_root:
            # Can't move files to the trash from within the trash root.
            # But a fallback root may be OK.
            continue  # makes things easier
        subdirs = [join(trash_root, s) for s in ("files", "info")]
        subdirs_valid = True
        for subdir in subdirs:
            if not isdir(subdir):
                try:
                    os.makedirs(subdir, 0o700)
                except OSError:
                    subdirs_valid = False
            if not os.access(subdir, os.W_OK):
                subdirs_valid = False
        if subdirs_valid:
            return tuple([trash_root] + subdirs)
    raise TrashError("No valid trash folder exists for %r" % (path,))


def trash_free_desktop(path):
    """Partial implementation of
    http://www.freedesktop.org/wiki/Specifications/trash-spec

    This doesn't work for files in the trash directory.
    """

    path = abspath(path)

    if not exists(path):
        raise TrashError("Path %s does not exist." % path)

    trash_dir, files, info = _get_fd_trash_dirs(path)


    info_ext = ".trashinfo"
    name = basename(path)
    flags = os.O_EXCL | os.O_CREAT | os.O_WRONLY
    mode = 0o644
    try:
        info_path = join(info, name + info_ext)
        info_fd = os.open(info_path, flags, mode)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise
        i = 2
        while 1:
            head, tail = splitext(name)
            temp_name = "%s.%d%s" % (head, i, tail)
            info_path = join(info, temp_name + info_ext)
            try:
                info_fd = os.open(info_path, flags, mode)
            except OSError as e:
                if e.errno != errno.EEXIST:
                    raise
                i += 1
                continue
            name = temp_name
            break

    parent = dirname(trash_dir)
    if path.startswith(join(parent, "")):
        norm_path = path[len(join(parent, "")):]
    else:
        norm_path = path

    del_date = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())

    data = "[Trash Info]\n"
    data += "Path=%s\n" % urllib.pathname2url(norm_path)
    data += "DeletionDate=%s\n" % del_date
    os.write(info_fd, data)
    os.close(info_fd)

    target_path = join(files, name)
    try:
        shutil.move(path, target_path)
    except OSError:
        os.unlink(info_path)
        raise


def use_trash():
    """If the current platform supports moving files into a trash can."""
    return (
        os.name == "posix" and sys.platform != "darwin" and
        not config.getboolean("settings", "bypass_trash"))


def trash(path):
    if os.name == "posix" and sys.platform != "darwin":
        trash_free_desktop(path)
    else:
        raise NotImplementedError
