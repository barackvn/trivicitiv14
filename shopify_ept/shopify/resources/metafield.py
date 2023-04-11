from ..base import ShopifyResource


class Metafield(ShopifyResource):
    _prefix_source = "/$resource/$resource_id/"

    @classmethod
    def _prefix(cls, options={}):
        if resource := options.get("resource"):
            return f'{cls.site}/{resource}/{options["resource_id"]}'
        else:
            return cls.site
