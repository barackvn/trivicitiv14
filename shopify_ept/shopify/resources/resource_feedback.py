from ..base import ShopifyResource


class ResourceFeedback(ShopifyResource):
    _prefix_source = "/products/$product_id/"
    _plural = "resource_feedback"

    @classmethod
    def _prefix(cls, options={}):
        if product_id := options.get("product_id"):
            return f"{cls.site}/products/{product_id}"
        else:
            return cls.site
