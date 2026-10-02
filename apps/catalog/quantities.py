from decimal import Decimal, InvalidOperation

from apps.common.errors import DomainError


def presentation_quantity(presentation, units, *, milk_pilot=False):
    try:
        units = Decimal(str(units))
    except InvalidOperation:
        raise DomainError("VALIDATION_ERROR", "Cantidad inválida.", 422)
    if not units.is_finite() or units <= 0 or units > Decimal("99999999999.999"):
        raise DomainError("VALIDATION_ERROR", "Cantidad fuera de rango.", 422)
    if units.as_tuple().exponent < -3:
        raise DomainError("VALIDATION_ERROR", "Máximo tres decimales.", 422)
    if not presentation.active or not presentation.product.active:
        raise DomainError("VALIDATION_ERROR", "Presentación o producto inactivo.", 422)
    if not presentation.allows_fraction and units != units.to_integral_value():
        raise DomainError("VALIDATION_ERROR", "Las bolsas deben ser enteras.", 422)
    if milk_pilot and (
        presentation.product.unit_id != "L"
        or presentation.content_base != Decimal("1")
        or presentation.allows_fraction
    ):
        raise DomainError("VALIDATION_ERROR", "El piloto requiere bolsas indivisibles de 1 L.", 422)
    quantity = units * presentation.content_base
    if quantity > Decimal("99999999999.999") or quantity != quantity.quantize(Decimal("0.001")):
        raise DomainError("VALIDATION_ERROR", "Cantidad resultante fuera de precisión/rango.", 422)
    return quantity.quantize(Decimal("0.001"))
