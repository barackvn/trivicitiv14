from ..base import ShopifyResource
from .. import mixins


class Variant(ShopifyResource, mixins.Metafields):
    _prefix_source = "/products/$product_id/"

    @classmethod
    def _prefix(cls, options={}):
        if product_id := options.get("product_id"):
            return f"{cls.site}/products/{product_id}"
        else:
            return cls.site

    def save(self):
        if 'product_id' not in self._prefix_options:
            self._prefix_options['product_id'] = self.product_id

        start_api_version = '201910'
        api_version = ShopifyResource.version
        if api_version and (
                api_version.strip('-') >= start_api_version) and api_version != 'unstable':
            if 'inventory_quantity' in self.attributes:
                del self.attributes['inventory_quantity']
            if 'old_inventory_quantity' in self.attributes:
                del self.attributes['old_inventory_quantity']

        return super(ShopifyResource, self).save()
