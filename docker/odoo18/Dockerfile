# Odoo 18 Community image for the seven FMS modules.
# Build from the repository root: docker compose -f docker/odoo18/docker-compose.yml up --build
FROM odoo:18.0

USER root

COPY docker/odoo18/requirements.txt /tmp/fms-requirements.txt
RUN pip3 install --no-cache-dir --break-system-packages -r /tmp/fms-requirements.txt \
    && rm /tmp/fms-requirements.txt

COPY --chown=odoo:odoo apartment_management /mnt/extra-addons/apartment_management
COPY --chown=odoo:odoo esg_management /mnt/extra-addons/esg_management
COPY --chown=odoo:odoo gate_management /mnt/extra-addons/gate_management
COPY --chown=odoo:odoo owner_tenant_management /mnt/extra-addons/owner_tenant_management
COPY --chown=odoo:odoo property_management /mnt/extra-addons/property_management
COPY --chown=odoo:odoo resident_management /mnt/extra-addons/resident_management
COPY --chown=odoo:odoo workforce_management /mnt/extra-addons/workforce_management

USER odoo

EXPOSE 8069
