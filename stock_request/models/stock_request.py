# Copyright 2017-2020 ForgeFlow, S.L.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare

REQUEST_STATES = [
    ("draft", "Draft"),
    ("open", "In progress"),
    ("done", "Done"),
    ("cancel", "Cancelled"),
]


class StockRequest(models.Model):
    _name = "stock.request"
    _description = "Stock Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    @api.model
    def default_get(self, fields):
        res = super(StockRequest, self).default_get(fields)
        warehouse = None
        if "warehouse_id" not in res and res.get("company_id"):
            warehouse = self.env["stock.warehouse"].search(
                [("company_id", "=", res["company_id"])], limit=1
            )
        if warehouse:
            res["warehouse_id"] = warehouse.id
            res["location_id"] = warehouse.lot_stock_id.id
        return res

    def __get_request_states(self):
        return REQUEST_STATES

    def _get_request_states(self):
        return self.__get_request_states()

    def _get_default_requested_by(self):
        return self.env["res.users"].browse(self.env.uid)

    name = fields.Char(states={"draft": [("readonly", False)]})
    state = fields.Selection(
        selection=_get_request_states,
        string="Status",
        copy=False,
        default="draft",
        index=True,
        readonly=True,
        tracking=True,
    )
    requested_by = fields.Many2one(
        "res.users",
        required=True,
        tracking=True,
        default=lambda self: self.env.user,
    )
    request_date = fields.Datetime(index=True, required=True, readonly=True,
                                   default=fields.Date.today())

    picking_ids = fields.One2many("stock.picking","stock_request_id",
                                  # compute="_compute_picking_ids",
                                   string="Pickings",  readonly=True)
    picking_count = fields.Integer(
        string="Delivery Orders",
        compute="_compute_picking_ids",
        readonly=True,
    )
    warehouse_id = fields.Many2one("stock.warehouse", "Warehouse", ondelete="cascade", required=True)
    location_id = fields.Many2one(
        "stock.location",
        "Location",
        domain=[("usage", "in", ["internal", "transit"])],
        ondelete="cascade",
        required=True,
    )
    location_dest_id = fields.Many2one(
        "stock.location",
        "Destination",
        domain=[("usage", "in", ["internal", "transit"])],
        ondelete="cascade",
        required=True,
        )
    company_id = fields.Many2one("res.company", "Company", required=True, default=lambda self: self.env.company)
    request_line_ids = fields.One2many(
        "stock.request.line", inverse_name="request_id", copy=True
    )
    allow_virtual_location = fields.Boolean(
        related="company_id.stock_request_allow_virtual_loc", readonly=True
    )
    picking_type_id = fields.Many2one('stock.picking.type', string='Operation Type',
                                      domain=[('code', '=', 'internal')])
    branch_id = fields.Many2one('res.branch', string='Branch', default=lambda self: self.env.user.branch_id)

    _sql_constraints = [
        ("name_uniq", "unique(name, company_id)", "Stock Request name must be unique")
    ]

    @api.onchange('picking_type_id')
    def onchange_picking_type_id(self):
        if self.picking_type_id:
            self.location_dest_id = self.picking_type_id.default_location_dest_id

    @api.onchange("warehouse_id")
    def onchange_warehouse_id(self):
        """Finds location id for changed warehouse."""
        res = {"domain": {}}
        if self._name == "stock.request":
            # When the stock request is created from an order the wh and
            # location are taken from the order and we rely on it to change
            # all request associated. Thus, no need to apply
            # the onchange, as it could lead to inconsistencies.
            return res
        if self.warehouse_id:
            loc_wh = self.location_id.warehouse_id
            if self.warehouse_id != loc_wh:
                self.location_id = self.warehouse_id.lot_stock_id.id
            if self.warehouse_id.company_id != self.company_id:
                self.company_id = self.warehouse_id.company_id
        return res

    @api.onchange("location_id")
    def onchange_location_id(self):
        if self.location_id:
            loc_wh = self.location_id.warehouse_id
            if loc_wh and self.warehouse_id != loc_wh:
                self.warehouse_id = loc_wh
                self.with_context(no_change_childs=True).onchange_warehouse_id()

    @api.onchange("allow_virtual_location")
    def onchange_allow_virtual_location(self):
        if self.allow_virtual_location:
            return {"domain": {"location_id": []}}

    @api.onchange("company_id")
    def onchange_company_id(self):
        """Sets a default warehouse when the company is changed and limits
        the user selection of warehouses."""
        if self.company_id and (
                not self.warehouse_id or self.warehouse_id.company_id != self.company_id
        ):
            self.warehouse_id = self.env["stock.warehouse"].search(
                [("company_id", "=", self.company_id.id)], limit=1
            )
            self.onchange_warehouse_id()

        return {"domain": {"warehouse_id": [("company_id", "=", self.company_id.id)]}}



    # @api.depends(
    #     "allocation_ids",
    #     "allocation_ids.stock_move_id",
    #     "allocation_ids.stock_move_id.picking_id",
    # )
    def _compute_picking_ids(self):
        for request in self:
            request.picking_count = 0
            request.picking_count = len(request.picking_ids)

    def _action_confirm(self):
        self.write({"state": "open"})

    def action_confirm(self):
        self._action_confirm()
        return True

    def action_draft(self):
        self.write({"state": "draft"})
        return True

    def action_cancel(self):
        self.sudo().request_line_ids.mapped("move_ids")._action_cancel()
        self.write({"state": "cancel"})
        return True

    def action_done(self):
        self.write({"state": "done"})
        return True

    def action_create_picking(self):
        picking = {
            'partner_id': self.requested_by.partner_id.id,
            'picking_type_id': self.picking_type_id.id or False,
            'location_id': self.location_id.id,
            'location_dest_id': self.location_dest_id.id,
            'stock_request_id': self.id,
            'branch_id': self.branch_id.id
        }
        picking_id = self.env['stock.picking'].create(picking).id
        for line in self.request_line_ids:
            allocation_ids = [
                (
                    0,
                    0,
                    {
                        "requested_product_uom_qty": line.product_uom_qty,
                        'request_line_id': line.id
                    },
                )
            ]
            self.env['stock.move'].create({
                'name': self.name,
                'product_id': line.product_id.id,
                'product_uom': line.product_uom_id.id or line.product_id.uom_id.id,
                'product_uom_qty': line.product_uom_qty,
                'location_id': self.location_id.id,
                'location_dest_id': self.location_dest_id.id,
                'picking_id': picking_id,
                'request_line_id': line.id,
                'allocation_ids': allocation_ids
            })


    def action_view_transfer(self):
        action = self.env.ref("stock.action_picking_tree_all").read()[0]

        pickings = self.mapped("picking_ids")
        if len(pickings) > 1:
            action["domain"] = [("id", "in", pickings.ids)]
        elif pickings:
            action["views"] = [(self.env.ref("stock.view_picking_form").id, "form")]
            action["res_id"] = pickings.id
        return action

    @api.model
    def create(self, vals):
        upd_vals = vals.copy()
        if upd_vals.get("name", "/") == "/":
            upd_vals["name"] = self.env["ir.sequence"].next_by_code("stock.request")
        # if "order_id" in upd_vals:
        #     # order_id = self.env["stock.request.order"].browse(upd_vals["order_id"])
        #     upd_vals["expected_date"] = order_id.expected_date
        return super().create(upd_vals)

    def unlink(self):
        if self.filtered(lambda r: r.state != "draft"):
            raise UserError(_("Only requests on draft state can be unlinked"))
        return super(StockRequest, self).unlink()


class StockRequestLine(models.Model):
    _name = 'stock.request.line'

    product_id = fields.Many2one('product.product')
    product_uom_id = fields.Many2one('uom.uom', string='Unit of Measure')
    product_uom_category_id = fields.Many2one(related='product_id.uom_id.category_id')
    product_uom_qty = fields.Float(string='Qty')
    qty_in_progress = fields.Float(
        digits="Product Unit of Measure",
        readonly=True,
        compute="_compute_qty",
        store=True,
        help="Quantity in progress.",
    )
    qty_done = fields.Float(
        digits="Product Unit of Measure",
        readonly=True,
        compute="_compute_qty",
        store=True,
        help="Quantity completed",
    )
    qty_cancelled = fields.Float(
        digits="Product Unit of Measure",
        readonly=True,
        compute="_compute_qty",
        store=True,
        help="Quantity cancelled",
    )
    request_id = fields.Many2one('stock.request')
    state = fields.Selection(related='request_id.state', string="Status")
    allocation_ids = fields.One2many(
        comodel_name="stock.request.allocation",
        inverse_name="request_line_id",
        string="Stock Request Allocation",
    )
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    move_ids = fields.One2many('stock.move', 'request_line_id', string='Stock Moves')

    @api.onchange('product_id')
    def _onchange_product_id(self):
        self.product_uom_id = self.product_id.uom_id.id

    @api.constrains("product_uom_qty")
    def _check_qty(self):
        for rec in self:
            if rec.product_uom_qty <= 0:
                raise ValidationError(
                    _("Stock Request product quantity has to be strictly positive.")
                )

    @api.depends(
        "allocation_ids",
        "allocation_ids.stock_move_id.state",
        "allocation_ids.stock_move_id.move_line_ids",
        "allocation_ids.stock_move_id.move_line_ids.qty_done",
    )
    def _compute_qty(self):
        for request in self:
            done_qty = 0
            for allocation in request.allocation_ids:
                if allocation.stock_move_id.state == 'done':
                    done_qty += sum(allocation.stock_move_id.move_line_ids.mapped('qty_done'))

            open_qty = sum(request.allocation_ids.mapped("open_product_qty"))
            uom = request.product_id.uom_id
            request.qty_done = uom._compute_quantity(done_qty, request.product_uom_id)
            qty_in_progress = open_qty-done_qty if open_qty >0 else 0
            request.qty_in_progress = uom._compute_quantity(
                qty_in_progress, request.product_uom_id
            )
            request.qty_cancelled = (
                max(
                    0,
                    uom._compute_quantity(
                        request.product_uom_qty - done_qty - open_qty,
                        request.product_uom_id,
                    ),
                )
                if request.allocation_ids
                else 0
            )
        if self.product_uom_qty == self.qty_done:
            self.action_done()

    def check_done(self):
        precision = self.env["decimal.precision"].precision_get(
            "Product Unit of Measure"
        )
        for request in self:
            allocated_qty = sum(request.allocation_ids.mapped("allocated_product_qty"))
            qty_done = request.product_id.uom_id._compute_quantity(
                allocated_qty, request.product_uom_id
            )
            if (
                float_compare(
                    qty_done, request.product_uom_qty, precision_digits=precision
                )
                >= 0
            ):
                request.action_done()
            elif request._check_done_allocation():
                request.action_done()
        return True

    def action_done(self):
        self.write({"state": "done"})
        not_done_line = self.request_id.request_line_ids.filtered(lambda line: line.state not in ['done', 'cancel'])
        if len(not_done_line) == 0:
            self.request_id.state = 'done'

        return True

    def _check_done_allocation(self):
        precision = self.env["decimal.precision"].precision_get(
            "Product Unit of Measure"
        )
        self.ensure_one()
        return (
            self.allocation_ids
            and float_compare(self.qty_cancelled, 0, precision_digits=precision) > 0
        )

    @api.depends("allocation_ids", "allocation_ids.stock_move_id")
    def _compute_move_ids(self):
        for request in self:
            request.move_ids = request.allocation_ids.mapped("stock_move_id")


