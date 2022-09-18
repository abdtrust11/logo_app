# Part of Crypton Soft-tech.
{
    "name": "Point Of Sale Order Return Reason",
    "author": "Crypton Soft-tech",
    "support": "crypton.soft.tech@gmail.com",
    "category": "Point of Sale",
    "summary": "POS Return, Return Reason, Reason, Return Note , POS Note, POS Order Return Note, POS Order Return, POS Order Return Reason,Return Reason, Return Product,Order Return, pos return reason, order return reason",
    "description": """This module helps you to enter reason when return order. You can print reason in receipt. You can make reason compulsory when return product.""",
    "version": "15.0.1",
    "depends": ["point_of_sale"],
    "application": True,
    "data": [
             'views/pos_config.xml',
            ],
    'assets': {
        'point_of_sale.assets': [
            'cs_pos_order_return_reason/static/src/js/pos.js',
            'cs_pos_order_return_reason/static/src/css/pos.css',
            
        ],
        'web.assets_qweb': [
            'cs_pos_order_return_reason/static/src/xml/pos.xml'
        ]
    },
    "auto_install": False,
    "installable": True,
    "images": ["static/description/background.png", ],
    "price": 0,
    "currency": "EUR",
    "license": "OPL-1",
}
