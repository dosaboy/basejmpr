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
import os
import re
import shutil
import subprocess
import uuid
import random
import tempfile


from jinja2 import Environment, PackageLoader


def render_templates(ctxt, dom_path, dom_templates, local_path,
                     local_templates):
    env = Environment()
    env.loader = PackageLoader('domain', 'templates')
    # Expect to fail if exists
    os.makedirs(dom_path)
    for t in dom_templates:
        rt = env.get_template(t).render(**ctxt)
        with open(os.path.join(dom_path, t), 'w') as fd:
            fd.write(rt)

    for t in local_templates:
        rt = env.get_template(t).render(**ctxt)
        with open(os.path.join(local_path, t), 'w') as fd:
            fd.write(rt)


def generate_unicast_mac():
    first = 0xFE
    while first == 0xFE:
        first = random.randint(0, 255) & 0xFE

    return "%02x:%02x:%02x:%02x:%02x:%02x" % (first,
                                              random.randint(0, 255),
                                              random.randint(0, 255),
                                              random.randint(0, 255),
                                              random.randint(0, 255),
                                              random.randint(0, 255))


def domain_exists(name):
    out = subprocess.check_output(['virsh', 'list', '--all'])
    key = re.compile(r' %s ' % name)
    result = re.search(key, out)
    return result is not None and result.group(0).strip() == name


def create_domains(root, base_root, revision, num_domains, base_revisions,
                   domain_name_prefix, root_disk_size, ssh_lp_user,
                   force=False, skip_seed=False, snap_dict=None):
    if revision:
        rev = revision
    else:
        rev = str(max([int(k) for k in base_revisions.keys()]))

    backingfile = os.path.join(base_root, rev,
                               base_revisions[rev]['files'][0])

    if not num_domains:
        num_domains = 1

    name = domain_name_prefix or str(uuid.uuid4())
    for n in xrange(num_domains):
        if num_domains > 1:
            dom_name = '{}{}'.format(name, n)
        else:
            dom_name = name

        dom_path = os.path.join(root, dom_name)
        imgpath = os.path.join(dom_path, '{}.img'.format(dom_name))
        seedpath = os.path.join(dom_path, '{}-seed.img'.format(dom_name))
        dom_uuid = uuid.uuid4()
        print "INFO: creating domain '{}' with uuid '{}'".format(dom_name,
                                                                 dom_uuid)
        if os.path.isdir(dom_path):
            if not force:
                print("WARNING: domain path '{}' already exists - skipping "
                      "create".format(dom_path))
                continue
            else:
                print("INFO: domain path '{}' already exists - "
                      "overwriting".format(dom_path))
                shutil.rmtree(dom_path)
        elif domain_exists(dom_name) and not force:
            print("WARNING: domain '{}' already exists - skipping "
                  "create".format(dom_name))
            continue

        ctxt = {'name': dom_name,
                'ssh_user': ssh_lp_user,
                'uuid': dom_uuid,
                'backingfile': backingfile,
                'img_path': imgpath,
                'seed_path': seedpath,
                'mac_addr1': generate_unicast_mac(),
                'mac_addr2': generate_unicast_mac(),
                'size': root_disk_size,
                'classic_snaps': snap_dict.get('classic'),
                'stable_snaps': snap_dict.get('stable')}

        if skip_seed:
            del ctxt['seed_path']

        local_templates = ['snap_install.sh']
        dom_templates = ['create-new.sh', 'domain.xml']
        if not skip_seed:
            dom_templates += ['user-data', 'meta-data']

        tmpdir = tempfile.mkdtemp()
        try:
            render_templates(ctxt, dom_path, dom_templates, tmpdir,
                             local_templates)
            if any(snap_dict.values()):
                subprocess.check_output(
                    ['write-mime-multipart',
                     '--output={}/user-data.tmp'.format(tmpdir),
                     '{}/user-data'.format(dom_path),
                     '{}/snap_install.sh:text/x-shellscript'.format(tmpdir)])
                shutil.copy(os.path.join(tmpdir, 'user-data.tmp'),
                            os.path.join(dom_path, 'user-data'))
        except:
            shutil.rmtree(tmpdir)
            raise

        os.chmod(os.path.join(dom_path, 'create-new.sh'), 0o0755)
        try:
            os.chdir(dom_path)
            with open('/dev/null') as fd:
                subprocess.check_call(['./create-new.sh'], stdout=fd,
                                      stderr=fd)

            try:
                subprocess.check_output(['virsh', 'define', 'domain.xml'],
                                        stderr=subprocess.STDOUT)
            except subprocess.CalledProcessError as exc:
                msg = ("error: operation failed: domain '{}' already "
                       "exists with uuid ".format(dom_name))
                if msg in exc.output and force:
                    with open('/dev/null') as fd:
                        subprocess.check_call(['virsh', 'undefine', dom_name],
                                              stdout=fd, stderr=fd)
                        subprocess.check_call(['virsh', 'define',
                                               'domain.xml'],
                                              stdout=fd, stderr=fd)
                else:
                    raise
        except:
            print("\nERROR: domain '{}' create unsuccessful: deleting "
                  "{}".format(dom_name, dom_path))
            shutil.rmtree(dom_path)
            raise
