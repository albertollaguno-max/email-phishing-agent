import os
import json
import logging
from typing import Dict, Any, Tuple
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
Tu objetivo es analizar el contenido de un correo electrónico reenviado y determinar si es seguro o fraudulento.

Analiza los siguientes factores:
1. Urgencia injustificada o presión psicológica.
2. URLs sospechosas o que no coinciden con la organización suplantada.
3. Solicitud de credenciales, datos bancarios o información personal confidencial.
4. Errores gramaticales u ortográficos significativos en correos supuestamente oficiales.
5. Incongruencias en el remitente o el contexto del mensaje.

Debes proporcionar tu respuesta ESTRICTAMENTE en formato JSON. Nada más.
El JSON debe tener la siguiente estructura:
{
    "is_fraudulent": true|false,
    "confidence_level": "low"|"medium"|"high",
    "explanation": "Explicación breve de 2-4 frases detallando el porqué de tu decisión y los indicadores clave encontrados."
}
"""

def analyze_email_content(subject: str, sender: str, body: str) -> Tuple[Dict[str, Any], int, int, str]:
    """
    Analyzes email using Groq, and fallback to OpenRouter if Groq fails.
    Returns: (parsed_json, prompt_tokens, completion_tokens, provider_used)
    """
    email_content = f"ASUNTO: {subject}\nREMITENTE ORIGINAL: {sender}\n\nCUERPO DEL MENSAJE:\n{body}"
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": email_content}
    ]

    # Intentar con Groq
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
            
            # OpenRouter passes usage data just like OpenAI
            p_tokens = completion.usage.prompt_tokens if hasattr(completion, 'usage') else 0
            c_tokens = completion.usage.completion_tokens if hasattr(completion, 'usage') else 0
            
            return (parsed, p_tokens, c_tokens, "openrouter")
        except Exception as e:
            logger.error(f"OpenRouter analysis failed: {e}")
            raise Exception("All AI providers failed to analyze the email.")
            
    raise Exception("No AI clients configured properly.")
