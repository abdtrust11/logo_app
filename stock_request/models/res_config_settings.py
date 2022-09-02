# Copyright 2018 Creu Blanca
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    default_picking_type_id = fields.Many2one('stock.picking.type', string='Operation Type',
                                              domain=[('code', '=', 'internal')], default_model="stock.request",
                                              readonly=False)
