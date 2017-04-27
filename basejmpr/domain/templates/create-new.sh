#!/bin/bash -eux
img={{name}}.img
{%- if seed_path %}
seed={{name}}-seed.img
sudo rm -f ${img} ${seed}
cloud-localds ${seed} user-data meta-data
{%- else %}
sudo rm -f ${img}
{%- endif %}
virsh destroy {{name}} || true
virsh undefine {{name}} || true
{%- if backingfile %}
qemu-img create -b {{backingfile}} -f qcow2 $img {{root_size}}
{% else %}
qemu-img create -f qcow2 $img {{root_size}}
{%- endif %}
{%- for disk in disks %}
sudo rm -f {{disk['name']}}
qemu-img create -f qcow2 {{disk['name']}} {{disk['size']}}
{%- endfor %}
virt-install \
    --name={{name}} \
    --connect=qemu:///system --ram={{mem}} --vcpus={{vcpus}} --hvm \
    --virt-type=kvm \
    --pxe --boot {{boot_order}} \
    --graphics vnc --noautoconsole --os-type=linux --accelerate \
    --disk=${img},bus=virtio,cache=none,sparse=true \
    {%- for disk in disks %}
    --disk={{disk['name']}},bus=virtio,cache=none,sparse=true \
    {%- endfor %}
    {%- if seed_path %}
    --disk={{seed_path}},bus=virtio,format=raw,cache=none \
    {%- endif %}
    {%- for network in networks %}
    --network=network={{network}},model=virtio \
    {%- endfor %}
    --print-xml 2 > domain.xml

virsh define domain.xml
