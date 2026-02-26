FROM odoo:19.0

# Install extra dependencies if needed
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt || true

# Copy all custom addons to /mnt/custom-addons
COPY . /mnt/custom-addons

# Expose Odoo port
EXPOSE 8069

# Start Odoo
CMD ["odoo"]