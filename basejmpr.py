#!/usr/bin/env python2
# Author: Edward Hope-Morley (opentastic@gmail.com)
# Description: QEMU Base Image Management Utility
# Copyright (C) 2017 Edward Hope-Morley
#
# License:
#
# This file is part of basejmpr.
#
# basejmpr is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# basejmpr is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with basejmpr. If not, see <http://www.gnu.org/licenses/>.
import argparse
import os
import re
import shutil
import subprocess


def get_consumers_by_version(consumers):
    _c_by_v = {}
    for img_path in consumers:
        for d in consumers[img_path]:
            ver = d['version']
            entry = {'image': img_path,
                     'backing_file': d['backing_file']}
            if ver in _c_by_v:
                _c_by_v[ver].append(entry)
            else:
                _c_by_v[ver] = [entry]

    return _c_by_v


def get_consumers(root_dir, base_revs):
    consumers = {}
    for path in os.listdir(root_dir):
        newpath = os.path.join(root_dir, path)
        if os.path.isdir(newpath):
            for e in os.listdir(newpath):
                if e.endswith('.img'):
                    img = os.path.join(newpath, e)
                    info = subprocess.check_output(['qemu-img', 'info', img])
                    for l in info.split('\n'):
                        regex = r'^backing file: .+\(actual path: (.+)\)'
                        res = re.search(regex, l)
                        if res:
                            for b in base_revs:
                                name = os.path.basename(res.group(1))
                                version = os.path.dirname(res.group(1))
                                version = os.path.basename(version)
                                img_path = os.path.join(newpath, e)
                                backing_file = os.path.join(version, name)
                                for img in base_revs[b]['files']:
                                    if backing_file == os.path.join(b, img):
                                        entry = {'version': version,
                                                 'backing_file': backing_file}
                                        if img_path in consumers:
                                            consumers[img_path].append(entry)
                                        else:
                                            consumers[img_path] = [entry]

                                    elif img_path not in consumers:
                                        consumers[img_path] = []

    return consumers


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--path', '-p', type=str, default=None,
                        required=True)
    parser.add_argument('--series', '-s', type=str, default='xenial',
                        required=False)
    parser.add_argument('--create-new', '-n', action='store_true',
                        default=False)
    parser.add_argument('--revision', '-r', type=int, default=None,
                        required=False)
    args = parser.parse_args()

    SERIES = [args.series] or ['trusty', 'xenial']
    BACKERS = os.path.join(args.path, 'backing_files')
    BASE_REVISIONS = {}
    UNKNOWNS = {}

    if os.path.isdir(BACKERS) and os.listdir(BACKERS):
        for d in os.listdir(BACKERS):
            b = os.listdir(os.path.join(BACKERS, d))
            BASE_REVISIONS[d] = {'files': b}

    rev = args.revision
    if (not BASE_REVISIONS or (rev and not BASE_REVISIONS.get(str(rev))) or
            (args.create_new)):
        if not BASE_REVISIONS:
            rev = 1
        else:
            rev = max([int(k) for k in BASE_REVISIONS.keys()]) + 1

        newpath = os.path.join(BACKERS, str(rev))
        os.makedirs(newpath)
        try:
            for series in SERIES:
                img = '%s-server-cloudimg-amd64-disk1.img' % (series)
                url = ('https://cloud-images.ubuntu.com/%s/current/%s' %
                       (series, img))
                subprocess.check_output(['wget',
                                         '-O', os.path.join(newpath, img),
                                         url])
        except:
            shutil.rmtree(newpath)

    print "Available base revisions:"
    for v in BASE_REVISIONS:
        print "%s: %s" % (v, ', '.join(BASE_REVISIONS[v]['files']))

    consumers = get_consumers(args.path, BASE_REVISIONS)
    print "\nConsumers:"
    c_by_v = get_consumers_by_version(consumers)
    for v in c_by_v:
        if c_by_v[v]:
            for d in c_by_v[v]:
                print "%s: %s -b %s" % (v, d['image'], d['backing_file'])

    print "\nOrphans"
    for img in consumers:
        if not consumers[img]:
            print img
