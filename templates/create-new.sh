#!/bin/bash -eux
img={{name}}.img
seed={{name}}-seed.img
rm -f ${img} ${seed}
cloud-localds ${seed} user-data meta-data
qemu-img create -b {{backingfile}} -f qcow2 ${img} {{size}}
