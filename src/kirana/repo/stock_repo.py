from kirana.db.connection import get_session
from kirana.db.models import StockMovement


def _row_to_dict(movement: StockMovement) -> dict:
    return {
        "id": movement.id,
        "product_id": movement.product_id,
        "movement_type": movement.movement_type,
        "quantity": movement.quantity,
        "cost_price": movement.cost_price,
        "reference": movement.reference,
        "created_at": movement.created_at,
    }


def record_movement(
    product_id: int,
    movement_type: str,
    quantity: float,
    cost_price: int | None = None,
    reference: str | None = None,
) -> dict:
    with get_session() as session:
        movement = StockMovement(
            product_id=product_id,
            movement_type=movement_type,
            quantity=quantity,
            cost_price=cost_price,
            reference=reference,
        )
        session.add(movement)
        session.flush()
        return _row_to_dict(movement)


def get_movements(product_id: int | None = None) -> list[dict]:
    with get_session() as session:
        q = session.query(StockMovement)
        if product_id is not None:
            q = q.filter(StockMovement.product_id == product_id)
        movements = q.order_by(StockMovement.created_at.desc()).all()
        return [_row_to_dict(m) for m in movements]
