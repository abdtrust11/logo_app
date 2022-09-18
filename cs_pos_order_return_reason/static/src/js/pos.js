odoo.define("cs_pos_order_return_reason.pos", function (require) {
    "use strict";
    
    const PosComponent = require("point_of_sale.PosComponent");
    const { useListener } = require("web.custom_hooks");
    const Registries = require("point_of_sale.Registries");
    const ProductScreen = require("point_of_sale.ProductScreen");
    const TicketScreen = require("point_of_sale.TicketScreen");
    var models = require("point_of_sale.models");
    const AbstractAwaitablePopup = require("point_of_sale.AbstractAwaitablePopup");
    
    class csReturnReasonButton extends PosComponent {
        constructor() {
            super(...arguments);
            useListener("cs_return_reason", this.onClickTemplateLoad);
        }
        onClickTemplateLoad() {
        	let { confirmed, payload } = this.showPopup("TemplateOrderReturnPopupWidget");
            if (confirmed) {
            } else {
                return;
            }
        }
    }
    csReturnReasonButton.template = "csReturnReasonButton";
    ProductScreen.addControlButton({
        component: csReturnReasonButton,
        condition: function () {
            return this.env.pos.config.enable_order_return_reason && this.env.pos.get_order().is_refund_order;
        },
    });
    Registries.Component.add(csReturnReasonButton);
    
    const CsOrderReturnTicketScreen = (TicketScreen) =>
    class extends TicketScreen {
    	async _onDoRefund() {
            this.env.pos.get_order().is_refund_order = true;
            await super._onDoRefund();
        }
    };
    Registries.Component.extend(TicketScreen, CsOrderReturnTicketScreen);
    
    var _super_order = models.Order.prototype;
    models.Order = models.Order.extend({
        initialize: function () {
            var self = this;
            self.is_refund_order = false;
            self.reason = false;
            _super_order.initialize.apply(this, arguments);
        },
        set_order_return_reason: function(reason){
        	this.reason = reason
        },
        get_order_return_reason: function(){
        	return this.reason;
        },
        export_as_JSON: function () {
            var json = _super_order.export_as_JSON.apply(this, arguments);
            json.reason = this.get_order_return_reason() || null;

            return json;
        },
        export_for_printing: function () {
            var self = this;
            var orders = _super_order.export_for_printing.call(this);
            var new_val = {
            		reason: this.get_order_return_reason() || false,
            };
            $.extend(orders, new_val);
            return orders;
        },
    });
    
    class TemplateOrderReturnPopupWidget extends AbstractAwaitablePopup {
        constructor() {
            super(...arguments);
        }
        async confirm() {
            var self = this;
            this.props.resolve({ confirmed: true, payload: await this.getPayload() });
            this.trigger("close-popup");
            var value = $("#textarea_note").val();
            this.env.pos.get_order().set_order_return_reason(value);
        }
    }

    TemplateOrderReturnPopupWidget.template = "TemplateOrderReturnPopupWidget";
    Registries.Component.add(TemplateOrderReturnPopupWidget);
    
    const PosProductScreen = (ProductScreen) =>
    class extends ProductScreen {
        _onClickPay() {
        	if(this && this.env && this.env.pos && this.env.pos.config && this.env.pos.config.enable_order_return_reason && this.env.pos.config.is_reason_compulsory && this.env.pos.get_order() && this.env.pos.get_order().is_refund_order){
        		if(this.env.pos.get_order() && this.env.pos.get_order().get_order_return_reason()){
        			super._onClickPay()
        		}else{
        			alert("Please enter reason for return.")
        		}
        	}else{
        		super._onClickPay()
        	}
        }
    };
	Registries.Component.extend(ProductScreen, PosProductScreen);
    
});
