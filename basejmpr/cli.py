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

from domain.utils import create_domains


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
                        regex = r'^backing file: ([^\s]+)'
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


def create_revision(basedir, series_list, rev):
    newpath = os.path.join(basedir, rev)
    if os.path.isdir(newpath):
        raise Exception("Base revision '{}' already exists".format(rev))

    os.makedirs(newpath)
    os.makedirs(os.path.join(newpath, 'meta'))
    os.makedirs(os.path.join(newpath, 'targets'))
    try:
        for series in series_list:
            items = [{'url': ('https://cloud-images.ubuntu.com/%s/current/'
                              '%s-server-cloudimg-amd64-disk1.img' %
                              (series, series)),
                      'out': os.path.join(newpath, 'targets',
                                          '%s-server-cloudimg-amd64-disk1.img'
                                          % (series))},
                     {'url':
                      ('https://cloud-images.ubuntu.com/%s/current/'
                       'SHA256SUMS' % (series)),
                      'out': os.path.join(newpath, 'meta/SHA256SUMS')},
                     {'url': ('https://cloud-images.ubuntu.com/%s/current/'
                              '%s-server-cloudimg-amd64.manifest' %
                              (series, series)),
                      'out': os.path.join(newpath, 'meta/manifest')}]
            for item in items:
                subprocess.check_output(['wget', '-O', item['out'],
                                         item['url']])

            revs = get_revisions(basedir, rev=rev)
            with open(os.path.join(newpath, 'meta/SHA256SUMS')) as fd:
                for line in fd.readlines():
                    for target in revs[rev]['targets']:
                        if target in line:
                            link = os.path.join(newpath,
                                                line.partition(' ')[0])
                            target = os.path.join('targets', target)
                            subprocess.check_output(['ln', '-fs',
                                                     target, link])
    except:
        shutil.rmtree(newpath)
        raise


def get_revisions(basedir, rev=None):
    revisions = {}
    if os.path.isdir(basedir) and os.listdir(basedir):
        for r in os.listdir(basedir):
            if not rev or rev == r:
                rdir = os.path.join(basedir, r)
                contents = os.listdir(rdir)
                contents1 = [c for c in contents if
                             os.path.islink(os.path.join(rdir, c))]
                contents2 = os.listdir(os.path.join(rdir, 'targets'))
                revisions[r] = {'files': contents1,
                                'targets': contents2}

    return revisions


def get_link(basedir, v, f):
    return os.path.realpath(os.path.join(basedir, v, f))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--path', '-p', type=str, default=None,
                        required=True, help="Path to kvm images")
    parser.add_argument('--series', '-s', type=str, default='xenial',
                        required=False, help="Ubuntu series you want "
                        "to use")
    parser.add_argument('--create-revision', action='store_true',
                        default=False, help="Whether to create a new "
                        "revision if one does not already exist. If "
                        "--revision is provided will attempt to create that "
                        "revision otherwise highest rev + 1")
    parser.add_argument('--create-domain', action='store_true',
                        default=False, help="Create a new domain.")
    parser.add_argument('--num-domains', type=int, default=None,
                        required=False, help="Number of domains to "
                        "create. (requires --create-new-domains)")
    parser.add_argument('--domain-name-prefix', type=str, default=None,
                        required=False, help="Name to be used for new "
                        "domains created. If multiple domains are created "
                        "they will be suffixed with an integer counter.")
    parser.add_argument('--revision', '-r', type=str, default=None,
                        required=False, help="Backing file revision to "
                        "use.")
    parser.add_argument('--force', action='store_true', default=False,
                        required=False, help="Force actions such as "
                        "creating domains that already exist.")
    parser.add_argument('--no-domain-seed', action='store_true', default=False,
                        required=False, help="Do not seed new domains "
                        "with a cloud-init config-drive.")
    parser.add_argument('--domain-snaps', type=str, default=None,
                        required=False, help="Comma-delimited list of snaps "
                        "to install in domain(s) if creating new ones")
    parser.add_argument('--domain-snaps-classic', type=str, default=None,
                        required=False, help="Comma-delimited list of snaps "
                        "to install in domain(s) if creating new ones. These "
                        "snaps will be install using --classic mode")
    args = parser.parse_args()

    SERIES = [args.series] or ['trusty', 'xenial']
    BACKERS_BASEDIR = os.path.join(args.path, 'backing_files')
    BASE_REVISIONS = {}
    UNKNOWNS = {}

    if not os.path.isdir(args.path):
        raise Exception("Non-existent path '%s'" % (args.path))

    BASE_REVISIONS = get_revisions(BACKERS_BASEDIR)

    rev = args.revision
    if rev and not BASE_REVISIONS.get(rev) and not args.create_revision:
        raise Exception("Revision '{}' does not exist".format(rev))
    elif (not BASE_REVISIONS or (rev and not BASE_REVISIONS.get(rev)) or
            (args.create_revision)):
        if not BASE_REVISIONS:
            rev = '1'
        elif not rev:
            rev = max([int(k) for k in BASE_REVISIONS.keys()]) + 1

        create_revision(BACKERS_BASEDIR, SERIES, rev)

    # refresh
    BASE_REVISIONS = get_revisions(BACKERS_BASEDIR)
    filtered_revisions = get_revisions(BACKERS_BASEDIR, args.revision)

    print "Available base revisions:"
    if filtered_revisions:
        for v in sorted(filtered_revisions.keys(), key=lambda k: int(k)):
            files = ['{} ({})'.format(f, get_link(BACKERS_BASEDIR, v, f))
                     for f in filtered_revisions[v]['files']]
            print "{}: {}".format(v, ', '.join(files))
    else:
        print "-"

    consumers = get_consumers(args.path, BASE_REVISIONS)
    print "\nConsumers:"
    c_by_rev = get_consumers_by_version(consumers)
    empty = True
    if c_by_rev:
        for rev in c_by_rev:
            if not args.revision or args.revision == rev:
                if c_by_rev[rev]:
                    empty = False
                    for d in c_by_rev[rev]:
                        print "%s: %s -b %s" % (rev, d['image'],
                                                d['backing_file'])

    if empty:
        print "-"

    print "\nOrphans:"
    empty = True
    for img in consumers:
        if not consumers[img]:
            empty = False
            print img

    if empty:
        print "-"

    print ""

    if args.create_domain:
        snaps = {'classic': args.domain_snaps_classic,
                 'stable': args.domain_snaps}
        create_domains(args.path, BACKERS_BASEDIR, args.revision,
                       args.num_domains, BASE_REVISIONS,
                       args.domain_name_prefix, args.force,
                       args.no_domain_seed, snap_dict=snaps)
