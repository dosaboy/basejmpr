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
qemu-img create -b {{backingfile}} -f qcow2 $img 40G
virt-install \
    --name={{name}} \
    --connect=qemu:///system --ram={{mem}} --vcpus={{vcpus}} --hvm \
    --virt-type=kvm \
    --pxe --boot network,hd \
    --graphics vnc --noautoconsole --os-type=linux --accelerate \
    --disk=${img},bus=virtio,cache=none,sparse=true \
    {%- if seed_path %}
    --disk={{seed_path}},bus=virtio,format=raw,cache=none \
    {%- endif %}
    --network=network=maasnet,model=virtio \
    --network=network=maasnet2,model=virtio --print-xml 2 > domain.xml

virsh define domain.xml
