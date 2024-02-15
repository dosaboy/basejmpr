#!/bin/bash -eux
img={{name}}.img
{%- if seed_path %}
seed={{name}}-seed.img
sudo rm -f ${img} ${seed}
cloud-localds ${seed} user-data {{network_config}}
{%- else %}
sudo rm -f ${img}
{%- endif %}
{%- if backingfile %}
qemu-img create -F qcow2 -b {{backingfile}} -f qcow2 $img {{root_size}}
{% else %}
qemu-img create -f qcow2 $img {{root_size}}
{%- endif %}
{%- for disk in disks %}
sudo rm -f {{disk['name']}}
qemu-img create -f qcow2 {{disk['name']}} {{disk['size']}}
{%- endfor %}

