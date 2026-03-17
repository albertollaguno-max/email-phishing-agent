import os
import json
import logging
import re
from typing import Dict, Any, Tuple, List, Optional
from groq import Groq
from openai import OpenAI

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

AI_MODEL_GROQ = os.getenv("AI_MODEL_GROQ", "llama-3.3-70b-versatile")
AI_MODEL_OPENROUTER = os.getenv("AI_MODEL_OPENROUTER", "meta-llama/llama-3.3-70b-instruct")

# Clients initialization
groq_client = None
if GROQ_API_KEY:
    groq_client = Groq(api_key=GROQ_API_KEY)

openrouter_client = None
if OPENROUTER_API_KEY:
    openrouter_client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
    )

SYSTEM_PROMPT = """Eres un experto analista de ciberseguridad especializado en detectar emails fraudulentos (phishing, spoofing, scam).
Tu postura por defecto es DESCONFIANZA. Los emails que recibes han sido reenviados por usuarios PORQUE les parecen sospechosos. Por eso debes ser especialmente riguroso.

CONTEXTO IMPORTANTE DEL SISTEMA:
Los emails que analizas llegan a través de un sistema de reenvío: los usuarios reenvían a esta dirección los emails sospechosos que quieren que analices.
Por tanto, TODOS los emails tendrán cabeceras de reenvío (Fwd:, RV:, Forwarded message, etc.) y NUNCA debes considerar el reenvío en sí mismo como una señal de phishing.
Analiza ÚNICAMENTE el contenido del email original dentro del reenvío, ignorando completamente la capa de reenvío.

=== REGLA CRÍTICA: EMAILS DE FACTURACIÓN Y PAGOS ===
Los emails sobre facturas pendientes, pagos fallidos, renovaciones de servicio y suscripciones vencidas son EL VECTOR DE PHISHING MÁS COMÚN. Debes ser EXTREMADAMENTE SUSPICAZ con estos emails.
Marcas frecuentemente suplantadas: IONOS, Microsoft 365, Google Workspace, OVH, GoDaddy, PayPal, Amazon, Apple, bancos, operadores de hosting. Si un email dice ser de cualquiera de estas empresas solicitando acción de pago, trátalo con máxima desconfianza.

Factores de ALTO RIESGO que deben marcar el email como sospechoso:
- Que el email incluya plantillas HTML sofisticadas que imiten a empresas reales (el phishing moderno copia fielmente la imagen corporativa).
- Que se mencionen "facturas pendientes", "pagos fallidos", "cuenta suspendida", "suscripción vencida" o similares.
- Que se incluyan enlaces para "pagar ahora", "actualizar método de pago" o "ver factura".
- Que incluya IDs de factura/contrato genéricos o que no puedan verificarse.
- Que el remitente original sea "unknown" o no se pueda verificar (señal MUY sospechosa).

=== ANÁLISIS DETALLADO ===
Analiza los siguientes factores del email ORIGINAL:
1. Urgencia injustificada o presión psicológica ("pague antes de X fecha o se suspenderá su servicio").
2. URLs: examina CADA URL del mensaje. ¿El dominio real coincide con la marca que dice ser? Phishing usa dominios similares como ion0s.com, ionos-billing.com, etc.
3. Solicitud directa o indirecta de credenciales, datos bancarios o información personal.
4. Errores gramaticales u ortográficos (pero CUIDADO: el phishing moderno suele estar bien escrito).
5. Incongruencias entre el remitente declarado y el dominio real del email. Si from_address es "unknown", esto es MUY sospechoso.
6. ¿Es razonable que el destinatario reciba este email? Los usuarios no suelen recibir facturas de empresas sin haber contratado nada.
7. El hecho de que un email "parezca profesional" NO lo hace legítimo. Los kits de phishing modernos replican exactamente la imagen de marca.

=== PRINCIPIO DE PRECAUCIÓN ===
En caso de duda, marca el email como FRAUDULENTO. Es preferible un falso positivo (marcar como sospechoso un email legítimo) que un falso negativo (dejar pasar un phishing).

Debes proporcionar tu respuesta ESTRICTAMENTE en formato JSON. Nada más.
El JSON debe tener la siguiente estructura:
{
    "is_fraudulent": true|false,
    "confidence_level": "low"|"medium"|"high",
    "explanation": "Explicación breve de 2-4 frases detallando el porqué de tu decisión y los indicadores clave encontrados."
}
"""

# ─── Heuristic pre-analysis ───────────────────────────────────────────────
# These patterns are checked BEFORE the AI, and the results are included
# in the prompt to guide the AI towards correct classification.

HIGH_RISK_KEYWORDS = [
    # Payment / billing
    r'factura\s+pendiente', r'pago\s+fallido', r'pago\s+pendiente',
    r'aviso\s+de\s+pago', r'método\s+de\s+pago', r'actualizar\s+pago',
    r'payment\s+failed', r'invoice\s+due', r'billing\s+update',
    r'outstanding\s+balance', r'overdue\s+payment',
    # Account suspension
    r'cuenta\s+suspendida', r'servicio\s+suspendido', r'account\s+suspend',
    r'renovación.*requerida', r'sesión.*requerida', r'verificar.*cuenta',
    r'confirmar.*identidad', r'verify.*account',
    # Credential harvesting
    r'actualizar.*contraseña', r'restablecer.*contraseña', r'reset.*password',
    r'confirmar.*datos', r'iniciar.*sesión.*aquí',
]

SPOOFED_BRANDS = [
    'ionos', 'microsoft', 'office 365', 'o365', 'google', 'workspace',
    'ovh', 'godaddy', 'paypal', 'amazon', 'apple', 'netflix', 'dhl',
    'correos', 'fedex', 'ups', 'banco', 'santander', 'bbva', 'caixabank',
    'kutxabank', 'ing', 'coinbase', 'binance', 'opensea', 'dropbox',
    'docusign', 'adobe', 'zoom', 'linkedin', 'facebook', 'meta', 'instagram',
]

# Dangerous attachment extensions
DANGEROUS_EXTENSIONS = [
    # Executables
    '.exe', '.bat', '.cmd', '.com', '.scr', '.pif', '.msi', '.msp', '.mst',
    # Scripts
    '.js', '.jse', '.vbs', '.vbe', '.wsf', '.wsh', '.ps1', '.psm1',
    # Office with macros
    '.docm', '.xlsm', '.pptm', '.dotm', '.xltm',
    # Archives (often used to hide malware)
    '.iso', '.img',
    # Other
    '.hta', '.cpl', '.inf', '.reg', '.rgs', '.sct', '.shb', '.lnk',
]

# Known legitimate domains for commonly spoofed brands.
# If a brand is mentioned but URLs/sender don't use these domains → suspicious.
LEGITIMATE_DOMAINS = {
    'ionos': ['ionos.es', 'ionos.com', 'ionos.de', 'ionos.co.uk', 'ionos.fr', '1and1.com', '1and1.es', '1und1.de'],
    'microsoft': ['microsoft.com', 'office.com', 'live.com', 'outlook.com', 'hotmail.com', 'office365.com'],
    'google': ['google.com', 'google.es', 'googleapis.com', 'accounts.google.com'],
    'workspace': ['google.com', 'workspace.google.com'],
    'paypal': ['paypal.com', 'paypal.es', 'paypal.me'],
    'amazon': ['amazon.com', 'amazon.es', 'amazon.de', 'amazon.co.uk', 'amazonaws.com'],
    'apple': ['apple.com', 'icloud.com'],
    'netflix': ['netflix.com'],
    'ovh': ['ovh.com', 'ovh.es', 'ovhcloud.com'],
    'godaddy': ['godaddy.com', 'secureserver.net'],
    'dhl': ['dhl.com', 'dhl.de', 'dhl.es'],
    'correos': ['correos.es', 'correos.com'],
    'fedex': ['fedex.com'],
    'ups': ['ups.com'],
    'santander': ['bancosantander.es', 'santander.com', 'santander.es'],
    'bbva': ['bbva.com', 'bbva.es'],
    'caixabank': ['caixabank.es', 'caixabank.com', 'lacaixa.es'],
    'kutxabank': ['kutxabank.es', 'kutxabank.com'],
    'ing': ['ing.es', 'ing.com'],
    'coinbase': ['coinbase.com'],
    'binance': ['binance.com'],
    'opensea': ['opensea.io'],
    'dropbox': ['dropbox.com', 'dropboxmail.com'],
    'docusign': ['docusign.com', 'docusign.net'],
    'adobe': ['adobe.com'],
    'zoom': ['zoom.us', 'zoom.com'],
    'linkedin': ['linkedin.com'],
    'facebook': ['facebook.com', 'fb.com', 'facebookmail.com'],
    'meta': ['meta.com', 'facebook.com', 'instagram.com'],
    'instagram': ['instagram.com'],
}


def _extract_domain_from_url(url: str) -> Optional[str]:
    """Extract the registerable domain from a URL (e.g. 'https://www.ionos.es/path' -> 'ionos.es')."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return None
        # Get last 2 parts (or 3 for co.uk, com.es, etc.)
        parts = hostname.lower().split('.')
        # Handle two-part TLDs like co.uk, com.es, org.uk
        two_part_tlds = ['co.uk', 'com.es', 'org.uk', 'com.au', 'co.de', 'com.br', 'co.jp']
        if len(parts) >= 3:
            last_two = '.'.join(parts[-2:])
            if last_two in two_part_tlds:
                return '.'.join(parts[-3:])
        if len(parts) >= 2:
            return '.'.join(parts[-2:])
        return hostname
    except Exception:
        return None


def _extract_domain_from_email(email_addr: str) -> Optional[str]:
    """Extract domain from an email address string, handling 'Name <email>' format."""
    if not email_addr or email_addr.lower() == 'unknown':
        return None
    # Extract email from 'Name <email@domain.com>' format
    match = re.search(r'[\w.+-]+@([\w.-]+)', email_addr)
    if match:
        domain = match.group(1).lower()
        parts = domain.split('.')
        if len(parts) >= 2:
            return '.'.join(parts[-2:]) if len(parts) <= 3 else '.'.join(parts[-2:])
        return domain
    return None


def _check_domain_brand_match(domains: List[str], brand: str) -> bool:
    """Check if ANY of the provided domains match the legitimate domains for a brand."""
    legit = LEGITIMATE_DOMAINS.get(brand, [])
    if not legit:
        return True  # No known domains to check against, can't determine
    return any(d in legit for d in domains)


def _check_html_link_mismatches(body_html: str) -> List[str]:
    """
    Detect HTML links where the display text shows a different domain than the actual href.
    E.g.: <a href="https://malware.xyz">https://ionos.es/pay</a>
    This is one of the most common phishing tricks.
    """
    alerts = []
    if not body_html:
        return alerts

    # Find all <a href="URL">TEXT</a> patterns
    link_pattern = re.compile(
        r'<a\s[^>]*href\s*=\s*["\']?(https?://[^"\'>\s]+)["\']?[^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL
    )
    for match in link_pattern.finditer(body_html):
        href_url = match.group(1).strip()
        display_text = re.sub(r'<[^>]+>', '', match.group(2)).strip()  # Strip inner HTML tags

        # Check if display text looks like a URL
        display_url_match = re.search(r'https?://[^\s]+', display_text)
        if display_url_match:
            display_url = display_url_match.group(0)
            href_domain = _extract_domain_from_url(href_url)
            display_domain = _extract_domain_from_url(display_url)
            if href_domain and display_domain and href_domain != display_domain:
                alerts.append(
                    f"🚨 ALERTA CRÍTICA ENLACE ENGAÑOSO: El enlace muestra '{display_domain}' como texto "
                    f"pero realmente enlaza a '{href_domain}'. Esta es una técnica de phishing MUY COMÚN "
                    f"para engañar al usuario haciéndole creer que va a un sitio legítimo."
                )
        # Check if display text contains a brand name but href goes elsewhere
        else:
            display_lower = display_text.lower()
            href_domain = _extract_domain_from_url(href_url)
            if href_domain:
                for brand, legit_domains in LEGITIMATE_DOMAINS.items():
                    if brand in display_lower and href_domain not in legit_domains:
                        alerts.append(
                            f"⚠️ ALERTA ENLACE SOSPECHOSO: El texto del enlace menciona '{brand.upper()}' "
                            f"pero el enlace real apunta a '{href_domain}', que no es un dominio oficial."
                        )
                        break

    return alerts


def _check_display_name_spoofing(sender: str) -> List[str]:
    """
    Check if the sender display name impersonates a brand but the email domain doesn't match.
    E.g.: "IONOS" <random@phishing-site.xyz>
    """
    alerts = []
    if not sender or sender.lower() == 'unknown':
        return alerts

    # Extract display name and email separately
    from email.utils import parseaddr
    display_name, email_addr = parseaddr(sender)
    if not display_name or not email_addr:
        return alerts

    display_lower = display_name.lower()
    email_domain = _extract_domain_from_email(email_addr)
    if not email_domain:
        return alerts

    for brand, legit_domains in LEGITIMATE_DOMAINS.items():
        if brand in display_lower and email_domain not in legit_domains:
            alerts.append(
                f"🚨 ALERTA DISPLAY NAME SPOOFING: El nombre mostrado del remitente es '{display_name}' "
                f"(sugiere ser de {brand.upper()}) pero el email real es '{email_addr}' "
                f"con dominio '{email_domain}', que NO pertenece a {brand.upper()}. "
                f"El nombre visible de un email puede falsificarse fácilmente."
            )
            break

    return alerts


def _check_attachments(attachment_names: List[str]) -> List[str]:
    """Check for dangerous attachment types."""
    alerts = []
    for filename in attachment_names:
        if not filename:
            continue
        fname_lower = filename.lower()

        # Check dangerous extensions
        for ext in DANGEROUS_EXTENSIONS:
            if fname_lower.endswith(ext):
                alerts.append(
                    f"🚨 ALERTA ADJUNTO PELIGROSO: El email contiene un archivo adjunto '{filename}' "
                    f"con extensión '{ext}'. Este tipo de archivo puede contener malware o código ejecutable."
                )
                break

        # Check double extensions (e.g., factura.pdf.exe)
        parts = fname_lower.rsplit('.', 2)
        if len(parts) >= 3:
            double_ext = f".{parts[-2]}.{parts[-1]}"
            alerts.append(
                f"🚨 ALERTA EXTENSIÓN DOBLE: El archivo '{filename}' tiene una extensión doble '{double_ext}'. "
                f"Esta es una técnica usada para disfrazar archivos ejecutables como documentos."
            )

    return alerts


def _parse_auth_results(headers: dict) -> List[str]:
    """
    Parse SPF, DKIM, and DMARC results from email headers.
    Returns alerts for any authentication failures.
    """
    alerts = []
    if not headers:
        return alerts

    # Try multiple header names (different mail servers use different names)
    auth_header_names = ['authentication-results', 'arc-authentication-results']
    auth_header = ''
    for name in auth_header_names:
        values = headers.get(name, [])
        if values:
            auth_header = values[0] if isinstance(values, list) else values
            break

    # Also check Received-SPF header
    received_spf = headers.get('received-spf', [])
    if received_spf:
        spf_value = received_spf[0] if isinstance(received_spf, list) else received_spf
        if spf_value:
            auth_header += ' ' + spf_value

    if not auth_header:
        return alerts  # No auth headers found (common in forwarded emails)

    auth_lower = auth_header.lower()

    # Check SPF result
    spf_match = re.search(r'spf\s*=\s*(\w+)', auth_lower)
    if spf_match:
        spf_result = spf_match.group(1)
        if spf_result in ('fail', 'hardfail'):
            alerts.append(
                "🚨 ALERTA SPF FAIL: La verificación SPF ha FALLADO. El servidor que envió este email "
                "NO está autorizado por el dominio del remitente. Fuerte indicador de spoofing."
            )
        elif spf_result == 'softfail':
            alerts.append(
                "⚠️ ALERTA SPF SOFTFAIL: La verificación SPF ha dado softfail. El servidor que envió "
                "este email posiblemente no está autorizado por el dominio del remitente."
            )
        elif spf_result == 'none':
            alerts.append(
                "⚠️ ALERTA SPF NONE: El dominio del remitente no tiene registro SPF configurado. "
                "Las empresas legítimas suelen tener SPF configurado."
            )

    # Check DKIM result
    dkim_match = re.search(r'dkim\s*=\s*(\w+)', auth_lower)
    if dkim_match:
        dkim_result = dkim_match.group(1)
        if dkim_result == 'fail':
            alerts.append(
                "🚨 ALERTA DKIM FAIL: La firma DKIM ha FALLADO. El contenido del email puede haber "
                "sido manipulado o el email no proviene realmente del dominio que dice ser."
            )
        elif dkim_result == 'none':
            alerts.append(
                "⚠️ ALERTA DKIM NONE: El email no tiene firma DKIM. Las empresas legítimas "
                "suelen firmar sus emails con DKIM."
            )

    # Check DMARC result
    dmarc_match = re.search(r'dmarc\s*=\s*(\w+)', auth_lower)
    if dmarc_match:
        dmarc_result = dmarc_match.group(1)
        if dmarc_result == 'fail':
            alerts.append(
                "🚨 ALERTA DMARC FAIL: La verificación DMARC ha FALLADO. Ni SPF ni DKIM han pasado "
                "con alineación de dominio. Este es el indicador MÁS FUERTE de email fraudulento."
            )
        elif dmarc_result == 'none':
            alerts.append(
                "⚠️ ALERTA DMARC NONE: El dominio del remitente no tiene política DMARC. "
                "Las empresas grandes suelen tener DMARC configurado."
            )

    return alerts


def _run_heuristic_analysis(
    subject: str,
    sender: str,
    body: str,
    body_html: str = '',
    attachment_names: Optional[List[str]] = None,
    email_headers: Optional[dict] = None,
) -> List[str]:
    """
    Runs rule-based checks and returns a list of risk alerts to prepend to the AI prompt.
    """
    alerts = []
    combined = f"{subject} {body}".lower()

    # ── 1. High-risk keyword check ──────────────────────────────────────
    matched_keywords = []
    for pattern in HIGH_RISK_KEYWORDS:
        if re.search(pattern, combined, re.IGNORECASE):
            matched_keywords.append(pattern)
    if matched_keywords:
        alerts.append(
            f"⚠️ ALERTA HEURÍSTICA: El email contiene {len(matched_keywords)} patrón(es) de phishing de alta frecuencia "
            f"relacionados con facturación/pagos/cuentas. Estos patrones son los más usados en phishing."
        )

    # ── 2. Brand mention check (using word boundaries to avoid false positives) ──
    matched_brands = [b for b in SPOOFED_BRANDS if re.search(r'\b' + re.escape(b) + r'\b', combined)]
    if matched_brands:
        alerts.append(
            f"⚠️ ALERTA HEURÍSTICA: El email menciona marca(s) frecuentemente suplantadas: {', '.join(matched_brands).upper()}. "
            f"Estas marcas son objetivos habituales de campañas de phishing."
        )

    # ── 3. Sender domain verification ───────────────────────────────────
    sender_domain = _extract_domain_from_email(sender)
    if not sender or sender.lower() == 'unknown':
        alerts.append(
            "🚨 ALERTA CRÍTICA: El remitente original NO pudo ser extraído (unknown). "
            "Esto es altamente sospechoso, ya que un email legítimo debería tener un remitente claro e identificable."
        )
    elif sender_domain and matched_brands:
        # Verify sender domain matches the brand it claims to be
        for brand in matched_brands:
            if not _check_domain_brand_match([sender_domain], brand):
                legit = LEGITIMATE_DOMAINS.get(brand, [])
                alerts.append(
                    f"🚨 ALERTA CRÍTICA DE DOMINIO: El email dice ser de {brand.upper()} pero el dominio del remitente "
                    f"es '{sender_domain}', que NO coincide con los dominios oficiales conocidos: {', '.join(legit)}. "
                    f"Esto es un indicador FUERTE de phishing/spoofing."
                )

    # ── 4. URL extraction and domain verification ───────────────────────
    urls = re.findall(r'https?://[^\s<>"\'\)]+', body)
    url_domains = []
    for url in urls:
        domain = _extract_domain_from_url(url)
        if domain:
            url_domains.append(domain)

    if url_domains:
        unique_domains = list(set(url_domains))
        alerts.append(
            f"📋 DOMINIOS DETECTADOS EN URLS: {', '.join(unique_domains)}. "
            f"Verifica que estos dominios sean los oficiales de la empresa que dice enviar el email."
        )

        # Cross-check URL domains against claimed brands
        for brand in matched_brands:
            legit = LEGITIMATE_DOMAINS.get(brand, [])
            if legit:
                non_matching = [d for d in unique_domains if d not in legit
                                and not any(d.endswith('.' + ld) for ld in legit)]
                matching = [d for d in unique_domains if d in legit
                            or any(d.endswith('.' + ld) for ld in legit)]
                if non_matching and not matching:
                    alerts.append(
                        f"🚨 ALERTA CRÍTICA DE URLs: El email dice ser de {brand.upper()} pero NINGUNA de las URLs "
                        f"usa dominios oficiales ({', '.join(legit[:5])}). "
                        f"En su lugar usa: {', '.join(non_matching[:5])}. FUERTE indicador de phishing."
                    )
                elif non_matching:
                    alerts.append(
                        f"⚠️ ALERTA DE URLs MIXTAS: El email dice ser de {brand.upper()}. Algunos enlaces "
                        f"van a dominios oficiales ({', '.join(matching[:3])}) pero otros van a dominios externos "
                        f"({', '.join(non_matching[:5])}). Posible phishing sofisticado que mezcla URLs reales con maliciosas."
                    )

    # ── 5. Sender-URL domain consistency check ──────────────────────────
    if sender_domain and url_domains:
        unique_url_domains = list(set(url_domains))
        non_sender_domains = [d for d in unique_url_domains if d != sender_domain
                              and not d.endswith('.' + sender_domain)
                              and not sender_domain.endswith('.' + d)]
        if non_sender_domains and len(non_sender_domains) == len(unique_url_domains):
            alerts.append(
                f"⚠️ ALERTA DE INCONSISTENCIA: El dominio del remitente ({sender_domain}) NO coincide "
                f"con ninguno de los dominios de las URLs del email ({', '.join(non_sender_domains[:5])}). "
                f"En emails legítimos, el remitente y las URLs suelen pertenecer a la misma organización."
            )

    # ── 6. Suspicious URL patterns ──────────────────────────────────────
    for url in urls:
        url_lower = url.lower()
        # URL shorteners
        if any(shortener in url_lower for shortener in ['bit.ly', 'tinyurl', 'goo.gl', 't.co', 'ow.ly', 'rebrand.ly']):
            alerts.append(f"⚠️ ALERTA: URL acortada detectada: {url[:80]}. Empresas legítimas no usan acortadores de URLs.")
        # Cloud storage hosting
        if any(host in url_lower for host in ['s3.amazonaws.com', 'storage.googleapis.com', 'blob.core.windows.net', 'firebasestorage']):
            alerts.append(f"🚨 ALERTA: URL alojada en almacenamiento cloud genérico: {url[:120]}. Técnica de phishing muy común.")
        # IP-based URLs
        if re.search(r'https?://\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', url):
            alerts.append(f"🚨 ALERTA: URL basada en dirección IP detectada. Emails legítimos usan dominios, no IPs.")
        # Lookalike domains (typosquatting) for known brands
        domain = _extract_domain_from_url(url)
        if domain:
            for brand, legit_domains in LEGITIMATE_DOMAINS.items():
                if brand in combined:  # Only check brands mentioned in the email
                    for ld in legit_domains:
                        ld_name = ld.split('.')[0]  # e.g. 'ionos' from 'ionos.es'
                        # Check for typosquatting: domain contains the brand name but isn't the legit domain
                        if ld_name in domain and domain not in legit_domains:
                            alerts.append(
                                f"🚨 ALERTA CRÍTICA TYPOSQUATTING: La URL usa el dominio '{domain}' que se parece "
                                f"a '{ld}' (dominio oficial de {brand.upper()}) pero NO es el mismo. "
                                f"Esto es una técnica de phishing conocida como typosquatting."
                            )
                            break

    # ── 7. HTML link text vs href mismatch ──────────────────────────────
    html_alerts = _check_html_link_mismatches(body_html)
    alerts.extend(html_alerts)

    # ── 8. Display name spoofing ────────────────────────────────────────
    display_name_alerts = _check_display_name_spoofing(sender)
    alerts.extend(display_name_alerts)

    # ── 9. Dangerous attachments ────────────────────────────────────────
    if attachment_names:
        attachment_alerts = _check_attachments(attachment_names)
        alerts.extend(attachment_alerts)

    # ── 10. SPF/DKIM/DMARC authentication ───────────────────────────────
    if email_headers:
        auth_alerts = _parse_auth_results(email_headers)
        alerts.extend(auth_alerts)

    return alerts



def analyze_email_content(
    subject: str,
    sender: str,
    body: str,
    feedback_examples: Optional[List[Dict]] = None,
    body_html: str = '',
    attachment_names: Optional[List[str]] = None,
    email_headers: Optional[dict] = None,
) -> Tuple[Dict[str, Any], int, int, str]:
    """
    Analyzes email using Groq, and fallback to OpenRouter if Groq fails.
    feedback_examples: list of dicts with keys: subject, sender, body, is_fraudulent, explanation
    Returns: (parsed_json, prompt_tokens, completion_tokens, provider_used)
    """
    # Run heuristic pre-analysis (includes domain/URL checks, SPF/DKIM/DMARC, attachments, etc.)
    heuristic_alerts = _run_heuristic_analysis(
        subject, sender, body,
        body_html=body_html,
        attachment_names=attachment_names,
        email_headers=email_headers,
    )

    email_content = f"ASUNTO: {subject}\nREMITENTE ORIGINAL: {sender}\n\nCUERPO DEL MENSAJE:\n{body}"

    # Prepend heuristic alerts if any were found
    if heuristic_alerts:
        alerts_text = "\n".join(heuristic_alerts)
        email_content = (
            f"=== PRE-ANÁLISIS AUTOMÁTICO (reglas heurísticas) ===\n"
            f"{alerts_text}\n"
            f"=== FIN PRE-ANÁLISIS ===\n\n"
            f"{email_content}"
        )
        logger.info(f"Heuristic pre-analysis raised {len(heuristic_alerts)} alert(s) for subject: {subject}")

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    # Inject few-shot examples from human feedback (learning from corrections)
    if feedback_examples:
        messages.append({
            "role": "user",
            "content": "A continuación te muestro algunos ejemplos de análisis anteriores corregidos por humanos para que los uses como referencia:"
        })
        for ex in feedback_examples:
            ex_content = f"ASUNTO: {ex['subject']}\nREMITENTE ORIGINAL: {ex['sender']}\n\nCUERPO DEL MENSAJE:\n{ex['body'][:800]}"
            verdict = "FRAUDULENTO ✓ (confirmado por humano)" if ex['is_fraudulent'] else "LEGÍTIMO ✓ (confirmado por humano)"
            ex_result = json.dumps({
                "is_fraudulent": ex['is_fraudulent'],
                "confidence_level": "high",
                "explanation": ex.get('explanation', '') + f" [{verdict}]"
            }, ensure_ascii=False)
            messages.append({"role": "user", "content": ex_content})
            messages.append({"role": "assistant", "content": ex_result})

    # The actual query
    messages.append({"role": "user", "content": email_content})

    # Try Groq first
    if groq_client:
        try:
            logger.info("Attempting AI analysis via Groq...")
            completion = groq_client.chat.completions.create(
                model=AI_MODEL_GROQ,
                messages=messages,
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            raw_response = completion.choices[0].message.content
            parsed = json.loads(raw_response)
            return (
                parsed,
                completion.usage.prompt_tokens,
                completion.usage.completion_tokens,
                "groq"
            )
        except Exception as e:
            logger.warning(f"Groq analysis failed: {e}. Attempting fallback to OpenRouter.")

    # Fallback OpenRouter
    if openrouter_client:
        try:
            logger.info("Attempting AI analysis via OpenRouter (Fallback)...")
            completion = openrouter_client.chat.completions.create(
                model=AI_MODEL_OPENROUTER,
                messages=messages,
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            raw_response = completion.choices[0].message.content
            parsed = json.loads(raw_response)

            p_tokens = completion.usage.prompt_tokens if hasattr(completion, 'usage') else 0
            c_tokens = completion.usage.completion_tokens if hasattr(completion, 'usage') else 0

            return (parsed, p_tokens, c_tokens, "openrouter")
        except Exception as e:
            logger.error(f"OpenRouter analysis failed: {e}")
            raise Exception("All AI providers failed to analyze the email.")

    raise Exception("No AI clients configured properly.")

