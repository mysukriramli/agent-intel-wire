import logging
from typing import List, Dict, Any
import requests
from pydantic import BaseModel
from ingesters.utils import save_wire_data

logger = logging.getLogger("IntelWire.LLMEconomy")

# Priority model families to track
TRACKED_PROVIDERS = ["anthropic", "openai", "google", "meta-llama", "deepseek", "mistralai", "qwen"]

class ModelEconomics(BaseModel):
    model_id: str
    name: str
    provider: str
    context_window_tokens: int
    max_output_tokens: int
    prompt_cost_per_1m_usd: float
    completion_cost_per_1m_usd: float
    supports_tools: bool
    supports_structured_output: bool


def fetch_model_market_data() -> List[Dict[str, Any]]:
    url = "https://openrouter.ai/api/v1/models"
    try:
        res = requests.get(url, timeout=15)
        res.raise_for_status()
        return res.json().get("data", [])
    except Exception as e:
        logger.error(f"Failed to fetch OpenRouter model data: {e}")
        return []


def run():
    logger.info("Executing LLM Token Economy Wire...")
    raw_models = fetch_model_market_data()
    parsed_models: List[ModelEconomics] = []

    for m in raw_models:
        model_id = m.get("id", "")
        provider = model_id.split("/")[0] if "/" in model_id else "unknown"

        # Filter to priority model ecosystems
        if not any(provider.startswith(p) for p in TRACKED_PROVIDERS):
            continue

        pricing = m.get("pricing", {})
        try:
            # OpenRouter reports pricing per individual token -> Convert to $/1M tokens
            prompt_cost = float(pricing.get("prompt", 0.0)) * 1_000_000
            completion_cost = float(pricing.get("completion", 0.0)) * 1_000_000
        except (ValueError, TypeError):
            prompt_cost, completion_cost = 0.0, 0.0

        top_provider = m.get("top_provider", {})
        context_window = m.get("context_length", 0)
        max_output = top_provider.get("max_completion_tokens") or 4096

        supported_params = m.get("supported_parameters", [])
        has_tools = "tools" in supported_params or "functions" in supported_params
        has_json = "response_format" in supported_params

        parsed_models.append(ModelEconomics(
            model_id=model_id,
            name=m.get("name", model_id),
            provider=provider,
            context_window_tokens=context_window,
            max_output_tokens=max_output,
            prompt_cost_per_1m_usd=round(prompt_cost, 4),
            completion_cost_per_1m_usd=round(completion_cost, 4),
            supports_tools=has_tools,
            supports_structured_output=has_json
        ))

    # Sort descending by context window
    parsed_models.sort(key=lambda x: x.context_window_tokens, reverse=True)

    # Format markdown digest for agent prompt routing
    md_lines = [
        "# Real-Time Foundation Model Token Economy & Capabilities",
        "> Ground-truth pricing, context ceilings, and tool-calling capabilities for routing agents.\n",
        "| Model ID | Context | In $/1M \vert{} Out $/1M | Tools | JSON |",
        "| :--- | :--- | :--- | :--- | :--- | :--- |"
    ]
    for pm in parsed_models[:35]:
        tools_flag = "Yes" if pm.supports_tools else "No"
        json_flag = "Yes" if pm.supports_structured_output else "No"
        md_lines.append(
            f"| `{pm.model_id}` | {pm.context_window_tokens:,} | ${pm.prompt_cost_per_1m_usd:.2f} "
            f"| ${pm.completion_cost_per_1m_usd:.2f} | {tools_flag} | {json_flag} |"
        )

    save_wire_data(
        domain="llm_economy",
        payload_key="models",
        items=[pm.model_dump() for pm in parsed_models],
        markdown_brief="\n".join(md_lines)
    )
    logger.info(f"LLM Token Economy Wire published {len(parsed_models)} model profiles.")
