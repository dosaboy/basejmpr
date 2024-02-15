#!/bin/bash -eux
img={{name}}.img
virsh destroy {{name}} || true
virsh undefine {{name}} || true

virt-install \
    --name={{name}} \
    --osinfo=ubuntu{{series}} \
    --connect=qemu:///system --ram={{mem}} --cpu host --vcpus={{vcpus}} --hvm \
    --virt-type=kvm \
    --pxe --boot {{boot_order}} \
    --graphics vnc --noautoconsole --os-type=linux --accelerate \
    --disk=${img},bus={{primary_disk['bus']}},sparse=true \
    {%- for disk in disks %}
    --disk={{disk['name']}},bus={{disk['bus']}},sparse=true \
    {%- endfor %}
    {%- if seed_path %}
    --disk={{seed_path}},bus=virtio,format=raw \
    {%- endif %}
    {%- for network in networks %}
    --network=network={{network}},model=virtio \
    {%- endfor %}
    --print-xml 2 > domain.xml

virsh define domain.xml
