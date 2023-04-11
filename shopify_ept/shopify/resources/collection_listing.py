from ..base import ShopifyResource

class CollectionListing(ShopifyResource):
    _primary_key = "collection_id"

    def product_ids(self, **kwargs):
        return self.get('product_ids', **kwargs)
