FROM odoo:19

USER root

# Copy custom addons
COPY . /mnt/extra-addons/

# Set permissions
RUN chown -R odoo:odoo /mnt/extra-addons/ && \
    if grep -q '^addons_path' /etc/odoo/odoo.conf; then \
        sed -i 's|^addons_path *=.*|addons_path=/mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons|' /etc/odoo/odoo.conf; \
    else \
        echo 'addons_path=/mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons' >> /etc/odoo/odoo.conf; \
    fi

USER odoo