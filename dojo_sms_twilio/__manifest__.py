{
    "name": "Dojo SMS Twilio",
    "version": "19.0.1.0.0",
    "summary": "Routes Odoo SMS through Twilio — overrides sms.api provider",
    "author": "Dojo",
    "category": "Hidden",
    "license": "LGPL-3",
    "depends": ["sms", "mail", "base_setup"],
    "data": [
        "data/ir_config_parameter.xml",
        "views/res_config_settings.xml",
    ],
    "installable": True,
    "auto_install": False,
}
