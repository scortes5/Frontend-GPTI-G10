"""Lectura y validación de formularios. La usan las páginas (envío normal) y la API de la cola (JSON),
así un lote guardado sin conexión pasa por las mismas reglas que uno enviado en línea.

Cada función devuelve (datos, error): si hay error, datos es None.
"""
from datetime import date

import sesion


class DatosInvalidos(ValueError):
    pass


def _texto(datos, campo: str, nombre: str, maximo: int) -> str:
    valor = str(datos.get(campo) or "").strip()
    if not valor:
        raise DatosInvalidos(f"Completa el campo {nombre}.")
    if len(valor) > maximo:
        raise DatosInvalidos(f"{nombre.capitalize()} admite hasta {maximo} caracteres.")
    if any(ord(c) < 32 or ord(c) == 127 for c in valor):
        raise DatosInvalidos(f"{nombre.capitalize()} no puede tener saltos de línea.")
    return valor


def _positivo(datos, campo: str, nombre: str) -> float:
    crudo = str(datos.get(campo) or "").strip().replace(" ", "")
    if "," in crudo:  # acepta 12,5 y 1.234,5
        crudo = crudo.replace(".", "").replace(",", ".")
    try:
        valor = float(crudo)
    except ValueError:
        raise DatosInvalidos(f"Escribe un número válido en {nombre}.") from None
    if valor <= 0 or valor != valor or valor == float("inf"):
        raise DatosInvalidos(f"{nombre.capitalize()} debe ser mayor que cero.")
    return round(valor, 3)


def _fecha(datos, campo: str, nombre: str) -> str:
    try:
        valor = date.fromisoformat(str(datos.get(campo) or ""))
    except ValueError:
        raise DatosInvalidos(f"Elige la {nombre}.") from None
    if valor > date.today():
        raise DatosInvalidos(f"La {nombre} no puede ser futura.")
    return valor.isoformat()


def _resultado(funcion):
    def envoltura(*args, **kwargs):
        try:
            return funcion(*args, **kwargs), None
        except DatosInvalidos as e:
            return None, str(e)

    return envoltura


@_resultado
def lote(datos) -> dict:
    # Un productor siempre registra a su nombre (el backend también lo fuerza).
    productor = _texto(datos, "productor", "productor", 120) if sesion.es_admin() else sesion.usuario()["nombre"]
    return {
        "productor": productor,
        "cultivo": _texto(datos, "cultivo", "cultivo", 80),
        "kilos": _positivo(datos, "kilos", "kilos"),
        "fecha_cosecha": _fecha(datos, "fecha_cosecha", "fecha de cosecha"),
    }


@_resultado
def venta(datos) -> dict:
    return {
        "comprador": _texto(datos, "comprador", "comprador", 120),
        "kilos": _positivo(datos, "kilos", "kilos"),
        "precio_por_kilo": _positivo(datos, "precio_por_kilo", "precio por kilo"),
        "fecha": _fecha(datos, "fecha", "fecha de venta"),
    }


@_resultado
def usuario_nuevo(datos) -> dict:
    clave = str(datos.get("clave") or "")
    if not 8 <= len(clave) <= 128:
        raise DatosInvalidos("La contraseña inicial debe tener entre 8 y 128 caracteres.")
    rol = datos.get("rol")
    if rol not in ("admin", "productor"):
        raise DatosInvalidos("Elige un rol.")
    return {
        "nombre": _texto(datos, "nombre", "nombre", 120),
        "email": _texto(datos, "email", "correo", 254),
        "clave": clave,
        "rol": rol,
    }
