#!/bin/bash -eux
img={{name}}.img
{%- if seed_path %}
seed={{name}}-seed.img
rm -f ${img} ${seed}
cloud-localds ${seed} user-data meta-data
{%- else %}
rm -f ${img}
{%- endif %}
qemu-img create -b {{backingfile}} -f qcow2 ${img} {{size}}
