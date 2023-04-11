from ..base import ShopifyResource
from .discount_code import DiscountCode

class DiscountCodeCreation(ShopifyResource):
    _prefix_source = "/price_rules/$price_rule_id/"

    def discount_codes(self):
        return DiscountCode.find(
            from_=f"{ShopifyResource.site}/price_rules/{self._prefix_options['price_rule_id']}/batch/{self.id}/discount_codes.{DiscountCodeCreation.format.extension}"
        )
