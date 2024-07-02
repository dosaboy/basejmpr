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
import collections
import os
import re
import shutil
import subprocess

from basejmpr.domain.utils import create_domains


def get_consumers_by_version(consumers):
    _c_by_v = {}
    for img_path in consumers:
        d = consumers[img_path]
        ver = d.get('version')
        if ver:
            entry = {'image': img_path,
                     'backing_file': d['backing_file']}
            if ver in _c_by_v:
                _c_by_v[ver].append(entry)
            else:
                _c_by_v[ver] = [entry]

    return collections.OrderedDict(sorted(_c_by_v.items(),
                                          key=lambda t: t[0]))


def get_consumers(root_dir, base_revs):
    consumers = {}
    for path in os.listdir(root_dir):
        newpath = os.path.join(root_dir, path)
        if os.path.isdir(newpath):
            for item in os.listdir(newpath):
                img_path = os.path.join(newpath, item)
                try:
                    info = subprocess.check_output(['qemu-img', 'info',
                                                    img_path],
                                                   stderr=subprocess.STDOUT)
                    info = info.decode('utf-8')
                except subprocess.CalledProcessError:
                    continue

                for line in info.split('\n'):
                    regex = r'^backing file: ([^\s]+)'
                    res = re.search(regex, line)
                    if res:
                        for rev in base_revs:
                            name = os.path.basename(res.group(1))
                            version = os.path.dirname(res.group(1))
                            version = os.path.basename(version)
                            backing_file = os.path.join(version, name)
                            for img in base_revs[rev]['files']:
                                if backing_file == os.path.join(rev, img):
                                    entry = consumers.get(img_path, {})
                                    if entry.get('version'):
                                        msg = ("Duplicate consumer entry "
                                               "detected - {}".format(
                                                   img_path))
                                        raise Exception(msg)

                                    entry['version'] = version
                                    entry['backing_file'] = backing_file
                                    consumers[img_path] = entry
                                elif img_path not in consumers:
                                    consumers[img_path] = {}

    return consumers


def create_revision(basedir, series, rev):
    newpath = os.path.join(basedir, rev)
    if os.path.isdir(newpath):
        raise Exception("Base revision '{}' already exists".format(rev))

    os.makedirs(newpath)
    os.makedirs(os.path.join(newpath, 'meta'))
    os.makedirs(os.path.join(newpath, 'targets'))
    try:
        items = [{'url':
                  ('https://cloud-images.ubuntu.com/{}/current/'
                   'SHA256SUMS'.format(series)),
                  'out': os.path.join(newpath, 'meta/SHA256SUMS')},
                 {'url': ('https://cloud-images.ubuntu.com/{series}/current/'
                          '{series}-server-cloudimg-amd64.manifest'.
                          format(series=series)),
                  'out': os.path.join(newpath, 'meta/manifest')}]

        _url = ('https://cloud-images.ubuntu.com/{}/current/'
                '{}-server-cloudimg-amd64')
        _url_extra = ''
        if series >= 'trusty':
            _url_extra = '-disk1'

        items.append({'url': '{}{}.img'.format(_url.format(series, series),
                                               _url_extra),
                      'out': os.path.join(newpath, 'targets',
                                          '{}-server-cloudimg-amd64{}.img'.
                                          format(series, _url_extra))})

        for item in items:
            subprocess.check_output(['wget', '-O', item['out'],
                                     item['url']])
        revs = get_revisions(basedir, rev=rev)
        with open(os.path.join(newpath, 'meta/SHA256SUMS')) as fd:
            link = None
            for line in fd.readlines():
                for target in revs[rev]['targets']:
                    if target in line:
                        link = os.path.join(newpath,
                                            line.partition(' ')[0])
                        target = os.path.join('targets', target)
                        subprocess.check_output(['chattr', '-i',
                                                 os.path.join(newpath,
                                                              target)])
                        subprocess.check_output(['ln', '-fs',
                                                 target, link])
            if not link:
                raise Exception("Unable to create target link")
    except Exception:
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


def display_info(root_path, backers_path, revisions, required_rev,
                 show_detached=False):
    print("Available revisions:")
    if revisions:
        for v in sorted(revisions.keys(), key=lambda k: int(k)):
            files = ['{} <- {}'.format(f, get_link(backers_path, v, f))
                     for f in revisions[v]['files']]
            print("{}:{}".format(v, ', '.join(files)))
    else:
        print("-")

    consumers = get_consumers(root_path, revisions)
    print("\nConsumers:")
    c_by_rev = get_consumers_by_version(consumers)
    empty = True
    if c_by_rev:
        _rev = None
        for rev in c_by_rev:
            if not required_rev or required_rev == rev:
                if c_by_rev[rev]:
                    for d in c_by_rev[rev]:
                        if _rev != rev:
                            print("{}:".format(rev))

                        empty = False
                        print("  {}".format(d['image']))
                        _rev = rev

    if empty:
        print("-")

    if show_detached:
        print("\nDetached:")
        empty = True
        for img, consumer in consumers.items():
            if not consumer.get('version'):
                empty = False
                print("{}".format(img))

        if empty:
            print("-")

    print("")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--path', '-p', type=str,
                        default='/var/lib/libvirt/images',
                        required=False, help="Path to images")
    parser.add_argument('--series', '-s', type=str, default='jammy',
                        required=False, help="Ubuntu series you want "
                        "to use")
    parser.add_argument('--no-cleanup', action='store_true', default=False,
                        help="Skip cleanup on failure. Useful for debugging")
    parser.add_argument('--create-revision', action='store_true',
                        default=False, help="Create a new revision if one "
                        "does not already exist. Use --revision to create a "
                        "specific one otherwise uses highest available + 1")
    parser.add_argument('--show-detached', action='store_true', default=False,
                        help="Show qcow2 images that do not have a "
                        "revisioned backing file")
    parser.add_argument('--create', action='store_true',
                        default=False, help="Create a new domain.")
    parser.add_argument('--num-domains', type=int, default=None,
                        required=False, help="Number of domains to "
                        "create. (requires --create-new-domains)")
    parser.add_argument('--name', '-n', type=str, default=None,
                        required=False, help="Name to be used for new "
                        "domains created. If multiple domains are created "
                        "they will be suffixed with an integer counter.")
    parser.add_argument('--revision', '-r', type=str, default=None,
                        required=False, help="Backing file revision to "
                        "use.")
    parser.add_argument('--nic-prefix', type=str, default=None,
                        required=False, help="Network interface name prefix.")
    parser.add_argument('--force', action='store_true', default=False,
                        required=False, help="Force actions such as "
                        "creating domains that already exist.")
    parser.add_argument('--no-seed', action='store_true', default=False,
                        required=False, help="Do not seed new domains "
                        "with a cloud-init config-drive.")
    parser.add_argument('--snaps', type=str, default=None,
                        required=False, help="Comma-delimited list of snaps "
                        "to install in domain(s) if creating new ones")
    parser.add_argument('--snaps-classic', type=str, default=None,
                        required=False, help="Comma-delimited list of snaps "
                        "to install in domain(s) if creating new ones. These "
                        "snaps will be install using --classic mode")
    parser.add_argument('--root-disk-size', type=str, default='40G',
                        required=False, help="Size of root disk for new "
                        "domains")
    parser.add_argument('--ssh-lp-id', type=str, default=None,
                        required=False, help="LP user to import ssh key.")
    parser.add_argument('--memory', '-m', type=int, default=1024,
                        required=False, help="Domain mem size in MB.")
    parser.add_argument('--vcpus', '-c', type=int, default=1,
                        required=False, help="vCPU count.")
    parser.add_argument('--boot-order', type=str, default='network,hd',
                        help="Domain boot order list (comma-seperated list of "
                             "boot devices)")
    parser.add_argument('--networks', type=str, default='default',
                        help="Comma-seperated list of networks to bind domain "
                             "to. Note that these networks must already "
                             "exist.")
    parser.add_argument('--no-backingfile', default=False,
                        action='store_true',
                        help="Create root disk without a backing file.")
    parser.add_argument('--num-disks', type=int, default=None,
                        help="Number of disks to attach to each domain.")
    parser.add_argument('--apt-proxy', type=str,
                        default=None)
    parser.add_argument('--init-script', type=str, default=None)
    parser.add_argument('--user-data', type=str, default=None)
    parser.add_argument('--meta-data', type=str, default=None)
    parser.add_argument('--net-config', type=str, default=None)
    parser.add_argument('--disk-bus', type=str, default="virtio")
    args = parser.parse_args()

    root_path = os.path.realpath(args.path)
    series = args.series
    backers_path = os.path.join(root_path, 'backing_files')

    if not os.path.isdir(root_path):
        raise Exception("Non-existent path '%s'" % (root_path))

    revisions = get_revisions(backers_path)

    rev = args.revision
    if rev and not revisions.get(rev) and not args.create_revision:
        raise Exception("Revision '{}' does not exist".format(rev))

    if (not revisions or (rev and not revisions.get(rev)) or
            (args.create_revision)):
        if not revisions:
            rev = '1'
        elif not rev:
            rev = str(max((int(k) for k in revisions)) + 1)

        create_revision(backers_path, series, rev)

    # refresh
    filtered_revisions = get_revisions(backers_path, args.revision)
    if args.create:
        snaps = {'classic': args.snaps_classic,
                 'stable': args.snaps}
        revisions = get_revisions(backers_path)
        create_domains(root_path, backers_path, args.revision, series,
                       args.num_domains, revisions,
                       args.name, args.root_disk_size,
                       args.ssh_lp_id, args.memory,
                       args.vcpus, args.boot_order,
                       args.networks, args.num_disks,
                       args.apt_proxy, args.init_script,
                       args.user_data, args.meta_data,
                       args.net_config,
                       args.disk_bus,
                       args.force, args.no_seed,
                       args.no_backingfile,
                       args.no_cleanup,
                       nic_prefix=args.nic_prefix,
                       snap_dict=snaps)
        print("")  # blank line

    display_info(root_path, backers_path, filtered_revisions, args.revision,
                 show_detached=args.show_detached)
