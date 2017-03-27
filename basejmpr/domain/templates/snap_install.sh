#!/bin/bash -eu
{%- if classic_snaps %}
sudo snap install --classic {{classic_snaps}}
{%- elif stable_snaps %}
sudo snap install {{stable_snaps}}
{%- endif %}
