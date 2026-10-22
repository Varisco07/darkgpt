"""Validatore JSON Schema minimale (sottoinsieme).

Supporta: type, required, properties, additionalProperties, enum, items,
minimum/maximum, minLength/maxLength, minItems/maxItems, default.

E' un sottoinsieme deliberato: i tool dichiarano schemi semplici e
deterministicamente validabili, senza dipendenze esterne.
"""

from __future__ import annotations

from typing import Any

_TYPE_MAP: dict[str, tuple[type, ...]] = {
    "string": (str,),
    "number": (int, float),
    "integer": (int,),
    "boolean": (bool,),
    "array": (list,),
    "object": (dict,),
    "null": (type(None),),
}


class SchemaValidationError(ValueError):
    """Errore di validazione dello schema con dettaglio sul percorso."""

    def __init__(self, errors: list[str]) -> None:
        super().__init__("; ".join(errors))
        self.errors = errors


def _type_ok(value: Any, expected: str) -> bool:
    if expected == "boolean":
        return isinstance(value, bool)
    if expected in ("number", "integer") and isinstance(value, bool):
        # In JSON, True non e' un numero.
        return False
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    types = _TYPE_MAP.get(expected)
    if types is None:
        return True
    return isinstance(value, types)


def validate(instance: Any, schema: dict[str, Any], path: str = "$") -> list[str]:
    """Valida un'istanza e restituisce la lista degli errori (vuota se valida)."""
    errors: list[str] = []
    if not schema:
        return errors

    expected_type = schema.get("type")
    if expected_type is not None:
        candidates = expected_type if isinstance(expected_type, list) else [expected_type]
        if not any(_type_ok(instance, candidate) for candidate in candidates):
            errors.append(
                f"{path}: tipo atteso {candidates}, ricevuto {type(instance).__name__}"
            )
            return errors

    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: valore {instance!r} non ammesso (ammessi: {schema['enum']})")

    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errors.append(f"{path}: lunghezza minima {schema['minLength']} non rispettata")
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            errors.append(f"{path}: lunghezza massima {schema['maxLength']} superata")

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{path}: valore minimo {schema['minimum']} non rispettato")
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append(f"{path}: valore massimo {schema['maximum']} superato")

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errors.append(f"{path}: numero minimo di elementi {schema['minItems']} non rispettato")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            errors.append(f"{path}: numero massimo di elementi {schema['maxItems']} superato")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(instance):
                errors.extend(validate(item, item_schema, f"{path}[{index}]"))

    if isinstance(instance, dict):
        properties = schema.get("properties", {})
        for required in schema.get("required", []):
            if required not in instance:
                errors.append(f"{path}: campo obbligatorio '{required}' mancante")
        additional = schema.get("additionalProperties", True)
        for key, value in instance.items():
            if key in properties:
                errors.extend(validate(value, properties[key], f"{path}.{key}"))
            elif additional is False:
                errors.append(f"{path}: campo non previsto '{key}'")
            elif isinstance(additional, dict):
                errors.extend(validate(value, additional, f"{path}.{key}"))
    return errors


def validate_or_raise(instance: Any, schema: dict[str, Any], path: str = "$") -> None:
    """Valida e solleva :class:`SchemaValidationError` in caso di problemi."""
    errors = validate(instance, schema, path)
    if errors:
        raise SchemaValidationError(errors)


def apply_defaults(instance: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    """Applica i valori di default dichiarati nelle proprietà."""
    result = dict(instance)
    for key, spec in schema.get("properties", {}).items():
        if key not in result and isinstance(spec, dict) and "default" in spec:
            result[key] = spec["default"]
    return result
