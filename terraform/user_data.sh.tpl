#!/bin/bash
dnf install -y nginx
echo '${html}' | base64 -d > /usr/share/nginx/html/index.html
systemctl enable --now nginx
