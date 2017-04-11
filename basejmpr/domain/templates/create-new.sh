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
virt-install \
    --name={{name}} \
    --connect=qemu:///system --ram={{mem}} --vcpus=1 --hvm --virt-type=kvm \
    --pxe --boot network,hd \
    --graphics vnc --noautoconsole --os-type=linux --accelerate \
    --disk=${img},bus=virtio,format=qcow2,cache=none,sparse=true,size=32 \
    {%- if seed_path %}
    --disk={{seed_path}},bus=virtio,format=raw,cache=none \
    {%- endif %}
    --network=network=maasnet,model=virtio \
    --network=network=maasnet2,model=virtio --print-xml 2 > domain.xml

virsh define domain.xml
