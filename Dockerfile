# Odoo 19 + FMS custom addons (official image supplies Odoo and core Python deps).
FROM odoo:19.0

USER root

# Optional extra pip deps for custom addons (kept minimal; see requirements.txt).
COPY requirements.txt /tmp/fms-requirements.txt
RUN set -eux; \
    if [ -s /tmp/fms-requirements.txt ] && grep -qvE '^[[:space:]]*(#|$)' /tmp/fms-requirements.txt; then \
      pip3 install --no-cache-dir --disable-pip-version-check -r /tmp/fms-requirements.txt; \
    fi; \
    rm -f /tmp/fms-requirements.txt

# All custom modules: legacy modules at repo root + FMS suite under addons/
COPY . /mnt/extra-addons/

COPY config/odoo.conf.example /etc/odoo/odoo.conf

USER odoo

# Default entrypoint/cmd from the official image (odoo server).
