from ..base import ShopifyResource

class UsageCharge(ShopifyResource):
    _prefix_source = "/recurring_application_charge/$recurring_application_charge_id/"

    @classmethod
    def _prefix(cls, options={}):
        if recurring_application_charge_id := options.get(
            "recurring_application_charge_id"
        ):
            return f"{cls.site}/recurring_application_charges/{recurring_application_charge_id}"
        else:
            return cls.site
