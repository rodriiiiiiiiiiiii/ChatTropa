from src.servicios import limpiar_texto_correo


def test_limpiar_texto_correo_firma_iphone():
    """Comprueba que recorta la firma automática de los móviles."""
    texto = "Hola, mi hijo sí va a la acampada.\n\nEnviado desde mi iPhone"
    resultado = limpiar_texto_correo(texto)
    assert resultado == "Hola, mi hijo sí va a la acampada."


def test_limpiar_texto_correo_historial_gmail():
    """Comprueba que recorta el historial de correos anteriores."""
    texto = "No podremos asistir, disculpad.\n\nEl 12 de abr. de 2024, Tropa Waconda escribió:\n> Queridas familias..."
    resultado = limpiar_texto_correo(texto)
    assert resultado == "No podremos asistir, disculpad."


def test_limpiar_texto_correo_limpio():
    """Si el correo no tiene firmas ni historiales, debe devolverlo intacto."""
    texto = "Hola, confirmo asistencia. Un saludo."
    resultado = limpiar_texto_correo(texto)
    assert resultado == "Hola, confirmo asistencia. Un saludo."
