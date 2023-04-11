from ..base import ShopifyResource
from .inventory_level import InventoryLevel

class Location(ShopifyResource):
    def inventory_levels(self, **kwargs):
        return InventoryLevel.find(
            from_=f"{ShopifyResource.site}/locations/{self.id}/inventory_levels.json",
            **kwargs,
        )
