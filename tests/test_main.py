from main import extraer_email_puro, es_spam_tecnico

def test_extraer_email_puro_con_nombre():
    """Prueba que limpia correctamente cuando Gmail añade el nombre del remitente."""
    remitente = "Papa de Juan <papa@gmail.com>"
    resultado = extraer_email_puro(remitente)
    assert resultado == "papa@gmail.com"

def test_extraer_email_puro_sin_nombre():
    """Prueba que funciona si solo viene el email directamente."""
    remitente = "mama@hotmail.com"
    resultado = extraer_email_puro(remitente)
    assert resultado == "mama@hotmail.com"

def test_extraer_email_puro_formato_raro():
    """Prueba el comportamiento de fallback si no hay un email válido."""
    remitente = "Remitente Oculto"
    resultado = extraer_email_puro(remitente)
    # Como tu Regex no encuentra un '@', devuelve el texto en minúsculas
    assert resultado == "remitente oculto"

def test_es_spam_tecnico_asunto():
    """Verifica que detecta un asunto de la Blacklist."""
    asunto = "⚠️ Tu almacenamiento de Gmail está lleno al 97 %"
    remitente = "info@google.com"
    assert es_spam_tecnico(asunto, remitente) == True

def test_es_spam_tecnico_remitente():
    """Verifica que detecta un remitente de la Blacklist."""
    asunto = "Actualización de políticas"
    remitente = "no-reply@google.com"
    assert es_spam_tecnico(asunto, remitente) == True

def test_es_spam_tecnico_correo_real():
    """Verifica que NO marca como spam un correo legítimo de un padre."""
    asunto = "Duda sobre la acampada"
    remitente = "papa_scout@gmail.com"
    assert es_spam_tecnico(asunto, remitente) == False