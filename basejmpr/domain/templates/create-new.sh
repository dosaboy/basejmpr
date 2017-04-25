#!/bin/bash -eux
img={{name}}.img
{%- if seed_path %}
seed={{name}}-seed.img
rm -f ${img} ${seed}
cloud-localds ${seed} user-data meta-data
{%- else %}
rm -f ${img}
{%- endif %}
virsh destroy {{name}} || true
virsh undefine {{name}} || true
qemu-img create -b {{backingfile}} -f qcow2 $img {{size}}
virt-install \
    --name={{name}} \
    --connect=qemu:///system --ram={{mem}} --vcpus={{vcpus}} --hvm \
    --virt-type=kvm \
    --pxe --boot {{boot_order}} \
    --graphics vnc --noautoconsole --os-type=linux --accelerate \
    --disk=${img},bus=virtio,cache=none,sparse=true \
    {%- if seed_path %}
    --disk={{seed_path}},bus=virtio,format=raw,cache=none \
    {%- endif %}
    {%- for network in networks %}
    --network=network={{network}},model=virtio \
    {%- endfor %}
    --print-xml 2 > domain.xml

virsh define domain.xml
