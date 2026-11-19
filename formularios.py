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


CALIDADES = ("extra", "primera", "segunda", "descarte")


def _opcional(datos, campo: str, nombre: str, maximo: int) -> str | None:
    return _texto(datos, campo, nombre, maximo) if str(datos.get(campo) or "").strip() else None


def _superficie(datos) -> float | None:
    if not str(datos.get("superficie_ha") or "").strip():
        return None
    valor = _positivo(datos, "superficie_ha", "superficie")
    if valor > 10_000:
        raise DatosInvalidos("Revisa la superficie: se escribe en hectáreas.")
    return valor


def _calidad(datos) -> str:
    calidad = str(datos.get("calidad") or "primera")
    if calidad not in CALIDADES:
        raise DatosInvalidos("Elige la calidad de la cosecha.")
    return calidad


def _motivo(datos) -> str:
    motivo = _texto(datos, "motivo", "motivo", 300)
    if len(motivo) < 3:
        raise DatosInvalidos("Explica el motivo en pocas palabras.")
    return motivo


def _productor(datos) -> str:
    # Un productor siempre registra a su nombre (el backend también lo fuerza).
    return _texto(datos, "productor", "productor", 120) if sesion.es_admin() else sesion.usuario()["nombre"]


@_resultado
def lote(datos) -> dict:
    return {
        "productor": _productor(datos),
        "cultivo": _texto(datos, "cultivo", "cultivo", 80),
        "predio": _opcional(datos, "predio", "predio", 120),
        "superficie_ha": _superficie(datos),
        "kilos": _positivo(datos, "kilos", "kilos"),
        "fecha_cosecha": _fecha(datos, "fecha_cosecha", "fecha de cosecha"),
        "calidad": _calidad(datos),
    }


@_resultado
def lote_edicion(datos) -> dict:
    """Los kilos no se editan: se corrigen con las entregas. Todo cambio lleva un motivo."""
    cambios = {
        "cultivo": _texto(datos, "cultivo", "cultivo", 80),
        "predio": _opcional(datos, "predio", "predio", 120),
        "superficie_ha": _superficie(datos),
        "fecha_cosecha": _fecha(datos, "fecha_cosecha", "fecha de la primera cosecha"),
        "motivo": _motivo(datos),
    }
    if sesion.es_admin():
        cambios["productor"] = _productor(datos)
    return cambios


@_resultado
def entrega(datos) -> dict:
    return {
        "fecha": _fecha(datos, "fecha", "fecha de entrega"),
        "kilos": _positivo(datos, "kilos", "kilos"),
        "calidad": _calidad(datos),
    }


@_resultado
def anulacion(datos) -> dict:
    return {"motivo": _motivo(datos)}


@_resultado
def venta(datos) -> dict:
    return {
        "comprador": _texto(datos, "comprador", "comprador", 120),
        "kilos": _positivo(datos, "kilos", "kilos"),
        "precio_por_kilo": _positivo(datos, "precio_por_kilo", "precio por kilo"),
        "fecha": _fecha(datos, "fecha", "fecha de venta"),
    }


def rut_valido(valor: str) -> str:
    """Revisa el dígito verificador (módulo 11) y devuelve el RUT como 12.345.678-5."""
    limpio = valor.replace(".", "").replace("-", "").replace(" ", "").upper()
    cuerpo, dv = limpio[:-1], limpio[-1:]
    if not (cuerpo.isdigit() and 6 <= len(cuerpo) <= 8 and dv):
        raise DatosInvalidos("Escribe el RUT con su dígito verificador, por ejemplo 12.345.678-5.")
    suma, factor = 0, 2
    for digito in reversed(cuerpo):
        suma += int(digito) * factor
        factor = 2 if factor == 7 else factor + 1
    esperado = {10: "K", 11: "0"}.get(11 - suma % 11, str(11 - suma % 11))
    if dv != esperado:
        raise DatosInvalidos("El RUT no es válido: revisa el dígito verificador.")
    return f"{int(cuerpo):,}".replace(",", ".") + f"-{dv}"


def _rol(datos) -> str:
    rol = datos.get("rol")
    if rol not in ("admin", "productor"):
        raise DatosInvalidos("Elige un rol.")
    return rol


@_resultado
def usuario_nuevo(datos) -> dict:
    """Sin contraseña, el sistema genera una. En ambos casos se envía al correo del socio."""
    clave = str(datos.get("clave") or "")
    if clave and not 8 <= len(clave) <= 128:
        raise DatosInvalidos("La contraseña inicial debe tener entre 8 y 128 caracteres, o déjala en blanco.")
    nuevo = {
        "nombre": _texto(datos, "nombre", "nombre", 120),
        "email": _texto(datos, "email", "correo", 254),
        "rut": rut_valido(_texto(datos, "rut", "RUT", 14)),
        "rol": _rol(datos),
    }
    if clave:
        nuevo["clave"] = clave
    return nuevo


@_resultado
def usuario_edicion(datos) -> dict:
    cambios = {
        "nombre": _texto(datos, "nombre", "nombre", 120),
        "email": _texto(datos, "email", "correo", 254),
        "rol": _rol(datos),
        "activo": datos.get("activo") == "si",
    }
    if str(datos.get("rut") or "").strip():
        cambios["rut"] = rut_valido(_texto(datos, "rut", "RUT", 14))
    return cambios


def _coordenada(datos, campo: str, nombre: str, minimo: float, maximo: float) -> float:
    crudo = str(datos.get(campo) or "").strip().replace(",", ".")
    try:
        valor = float(crudo)
    except ValueError:
        raise DatosInvalidos(f"Escribe la {nombre} como número (por ejemplo -38.74).") from None
    if not minimo <= valor <= maximo:
        raise DatosInvalidos(f"La {nombre} no corresponde a un lugar de Chile.")
    return round(valor, 6)


@_resultado
def campo(datos) -> dict:
    return {
        "nombre": _texto(datos, "nombre", "nombre del campo", 120),
        "latitud": _coordenada(datos, "latitud", "latitud", -56, -17),
        "longitud": _coordenada(datos, "longitud", "longitud", -76, -66),
    }
