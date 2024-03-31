"""Local business simulator. Reservations share the receipt transaction."""
from .identity import identifier


class Inventory:
    def __init__(self, store):
        self.store = store

    def provision(self, tenant, sku, available):
        identifier(sku, "SKU")
        if type(available) is not int or not 0 <= available <= 1000000:
            raise ValueError("Invalid inventory quantity")
        with self.store.transaction():
            if self.store.get(tenant, "inventory", sku):
                raise ValueError("Inventory already exists")
            self.store.put(tenant, "inventory", sku, {"sku": sku, "available": available})

    def reserve(self, tenant, request_id, arguments):
        self.store._write_required()
        sku, quantity = arguments.get("sku"), arguments.get("quantity")
        identifier(sku, "SKU")
        if set(arguments) != {"sku", "quantity"} or type(quantity) is not int or not 1 <= quantity <= 10:
            raise ValueError("Invalid reservation arguments")
        previous = self.store.get(tenant, "reservations", request_id)
        if previous:
            if previous["sku"] != sku or previous["quantity"] != quantity:
                raise ValueError("Reservation key already binds another effect")
            return previous
        stock = self.store.get(tenant, "inventory", sku)
        if not stock or stock["available"] < quantity:
            raise ValueError("Insufficient simulated inventory")
        stock["available"] -= quantity
        reservation = {"id": request_id, "sku": sku, "quantity": quantity, "available_after": stock["available"]}
        self.store.put(tenant, "inventory", sku, stock)
        self.store.put(tenant, "reservations", request_id, reservation)
        return reservation

    def list(self, tenant):
        return self.store.list(tenant, "inventory")
