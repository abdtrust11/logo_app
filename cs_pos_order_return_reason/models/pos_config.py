# Copyright (C) Crypton Soft-tech
from odoo import fields, models, api


class PosConfig(models.Model):
    _inherit = 'pos.config'

    enable_order_return_reason = fields.Boolean(
        "Allow to Enter Reason")
    
    display_reason_in_receipt = fields.Boolean(
        "Display Reason in Receipt")
    
    is_reason_compulsory = fields.Boolean(string="Is Reason Compulsory ?")
    
class PosOrder(models.Model):
    _inherit = 'pos.order'
    
    cs_return_reason = fields.Char(string="Return Reason")
    
    @api.model
    def _order_fields(self, ui_order):
        res = super(PosOrder, self)._order_fields(ui_order)
        res['cs_return_reason'] = ui_order.get('reason', False)
        return res
    