FROM odoo:latest

# Install extra dependencies into the system Python (must run as root)
USER root
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --break-system-packages -r /tmp/requirements.txt

# Copy all custom addons to /mnt/custom-addons
COPY . /mnt/custom-addons

# Expose Odoo port
EXPOSE 8069

# Start Odoo
CMD ["odoo"]