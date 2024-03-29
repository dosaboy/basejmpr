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
import tempfile


from jinja2 import Environment, PackageLoader


def render_templates(ctxt, dom_path, dom_templates, local_path,
                     local_templates):
    env = Environment()
    env.loader = PackageLoader('basejmpr.domain', 'templates')
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


def domain_exists(name):
    out = subprocess.check_output(['virsh', 'list', '--all']).decode('utf-8')
    key = re.compile(r' %s ' % name)
    result = re.search(key, out)
    return result is not None and result.group(0).strip() == name


def create_domains(root, base_root, revision, series, num_domains,
                   base_revisions, domain_name_prefix, root_disk_size,
                   ssh_lp_user, domain_memory, domain_vcpus, domain_boot_order,
                   networks, domain_disks, domain_apt_proxy,
                   domain_init_script, domain_user_data, domain_meta_data,
                   domain_net_config, domain_disk_bus,
                   force=False, skip_seed=False, skip_backingfile=False,
                   skip_cleanup=False, nic_prefix=None, snap_dict=None):

    rev = None
    if revision:
        rev = revision
    else:
        revs = sorted([int(idx) for idx in base_revisions.keys()],
                      reverse=True)
        for r in revs:
            r = str(r)
            _series = base_revisions[r]['targets'][0].partition('-')[0]
            if series and series == _series:
                rev = r
                break

    if not rev:
        raise Exception("No revision found for series '{}'".format(series))

    backingfile = os.path.join(base_root, rev,
                               base_revisions[rev]['files'][0])

    if not num_domains:
        num_domains = 1

    name = domain_name_prefix or str(uuid.uuid4())
    for n in range(num_domains):
        if num_domains > 1:
            dom_name = '{}{}'.format(name, n)
        else:
            dom_name = name

        dom_path = os.path.join(root, dom_name)
        imgpath = os.path.join(dom_path, '{}.img'.format(dom_name))
        seedpath = os.path.join(dom_path, '{}-seed.img'.format(dom_name))
        print("INFO: creating domain '{}'".format(dom_name))
        if os.path.isdir(dom_path):
            if not force:
                print("WARNING: domain path '{}' already exists - skipping "
                      "create".format(dom_path))
                continue

            print("INFO: domain path '{}' already exists - "
                  "overwriting".format(dom_path))
            shutil.rmtree(dom_path)
        elif domain_exists(dom_name) and not force:
            print("WARNING: domain '{}' already exists - skipping "
                  "create".format(dom_name))
            continue

        ctxt = {'name': dom_name,
                'series': series,
                'ssh_user': ssh_lp_user,
                'backingfile': backingfile,
                'img_path': imgpath,
                'seed_path': seedpath,
                'mem': domain_memory,
                'vcpus': domain_vcpus,
                'root_size': root_disk_size,
                'boot_order': domain_boot_order,
                'classic_snaps': snap_dict.get('classic'),
                'stable_snaps': snap_dict.get('stable'),
                'networks': networks.split(','),
                'apt_proxy': domain_apt_proxy,
                'nic_prefix': nic_prefix}

        if skip_backingfile:
            del ctxt['backingfile']

        if skip_seed:
            del ctxt['seed_path']

        ctxt['primary_disk'] = {'bus': domain_disk_bus}
        if domain_disks:
            disks = []
            for i in range(domain_disks):
                disks.append({'name': 'disk%s' % (i), 'size': '100G',
                              'bus': domain_disk_bus})

            ctxt['disks'] = disks

        local_templates = ['snap_install.sh']
        dom_templates = ['create-domain.sh', 'create-storage.sh']
        if not skip_seed:
            if not domain_user_data:
                dom_templates += ['user-data']

            if domain_meta_data:
                ctxt['network_config'] = 'meta-data'
            elif domain_net_config:
                ctxt['network_config'] = '--network-config network-config'
            else:
                ctxt['network_config'] = 'meta-data'
                dom_templates += ['meta-data']

        tmpdir = tempfile.mkdtemp()
        try:
            render_templates(ctxt, dom_path, dom_templates, tmpdir,
                             local_templates)

            if not skip_seed:
                for input, tgt in {domain_user_data: 'user-data',
                                   domain_meta_data: 'meta-data'}.items():
                    if input:
                        tgt = os.path.join(dom_path, tgt)
                        shutil.copy(input, tgt)

                write_multipart = False
                cmd = ['write-mime-multipart',
                       '--output={}/user-data.tmp'.format(tmpdir),
                       '{}/user-data'.format(dom_path)]
                if any(snap_dict.values()):
                    write_multipart = True
                    cmd.append('{}/snap_install.sh:text/x-shellscript'
                               .format(tmpdir))

                if domain_init_script:
                    write_multipart = True
                    cmd.append('{}:text/x-shellscript'
                               .format(domain_init_script))

                if write_multipart:
                    subprocess.check_output(cmd)
                    shutil.copy(os.path.join(tmpdir, 'user-data.tmp'),
                                os.path.join(dom_path, 'user-data'))

                if domain_net_config:
                    shutil.copy(domain_net_config,
                                os.path.join(dom_path, 'network-config'))
        except Exception:
            if not skip_cleanup:
                shutil.rmtree(tmpdir)

            raise

        os.chmod(os.path.join(dom_path, 'create-domain.sh'), 0o0755)
        os.chmod(os.path.join(dom_path, 'create-storage.sh'), 0o0755)
        try:
            os.chdir(dom_path)
            with open('/dev/null') as fd:
                subprocess.check_call(['./create-storage.sh'], stdout=fd,
                                      stderr=fd)
                subprocess.check_call(['./create-domain.sh'], stdout=fd,
                                      stderr=fd)
        except Exception:
            print("\nERROR: domain '{}' create unsuccessful: deleting "
                  "{}".format(dom_name, dom_path))
            if not skip_cleanup:
                shutil.rmtree(dom_path)

            raise
