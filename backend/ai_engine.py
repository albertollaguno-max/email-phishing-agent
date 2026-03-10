import os
import json
import logging
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

CONTEXTO IMPORTANTE DEL SISTEMA:
Los emails que analizas llegan a través de un sistema de reenvío: los usuarios reenvían a esta dirección los emails sospechosos que quieren que analices.
Por tanto, TODOS los emails tendrán cabeceras de reenvío (Fwd:, Forwarded message, etc.) y NUNCA debes considerar el reenvío en sí mismo como una señal de phishing.
Analiza ÚNICAMENTE el contenido del email original dentro del reenvío, ignorando completamente la capa de reenvío.

Analiza los siguientes factores del email ORIGINAL:
1. Urgencia injustificada o presión psicológica.
2. URLs sospechosas o que no coinciden con la organización que pretende ser el remitente.
3. Solicitud de credenciales, datos bancarios o información personal confidencial.
4. Errores gramaticales u ortográficos significativos en correos supuestamente oficiales.
5. Incongruencias entre el remitente declarado y el dominio real del email.
6. Contexto del asunto y del cuerpo: ¿es coherente con una comunicación legítima?

Debes proporcionar tu respuesta ESTRICTAMENTE en formato JSON. Nada más.
El JSON debe tener la siguiente estructura:
{
    "is_fraudulent": true|false,
    "confidence_level": "low"|"medium"|"high",
    "explanation": "Explicación breve de 2-4 frases detallando el porqué de tu decisión y los indicadores clave encontrados."
}
"""



def analyze_email_content(
    subject: str,
    sender: str,
    body: str,
    feedback_examples: Optional[List[Dict]] = None
) -> Tuple[Dict[str, Any], int, int, str]:
    """
    Analyzes email using Groq, and fallback to OpenRouter if Groq fails.
    feedback_examples: list of dicts with keys: subject, sender, body, is_fraudulent, explanation
    Returns: (parsed_json, prompt_tokens, completion_tokens, provider_used)
    """
    email_content = f"ASUNTO: {subject}\nREMITENTE ORIGINAL: {sender}\n\nCUERPO DEL MENSAJE:\n{body}"

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

