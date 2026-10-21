import os
import json
import logging
from typing import List, Dict, Any, Optional
import requests
from pydantic import BaseModel, Field
from ingesters.utils import save_wire_data

logger = logging.getLogger("IntelWire.SDKDiff")

# Repositories frequently generating hallucinated code in LLMs
TARGET_REPOSITORIES = [
    {"package": "pydantic", "owner": "pydantic", "repo": "pydantic", "ecosystem": "python"},
    {"package": "langchain", "owner": "langchain-ai", "repo": "langchain", "ecosystem": "python"},
    {"package": "openai", "owner": "openai", "repo": "openai-python", "ecosystem": "python"},
    {"package": "next", "owner": "vercel", "repo": "next.js", "ecosystem": "npm"},
    {"package": "transformers", "owner": "huggingface", "repo": "transformers", "ecosystem": "python"},
]

class BreakingChange(BaseModel):
    package: str
    ecosystem: str
    version: str
    deprecated_symbol: str
    replacement_symbol: str
    change_type: str = Field(description="breaking_change, deprecated_method, or structural_migration")
    syntax_before: str
    syntax_after: str
    summary: str


def fetch_github_releases(owner: str, repo: str) -> List[Dict[str, Any]]:
    """Fetches the 3 most recent releases using GitHub REST API."""
    url = f"https://api.github.com/repos/{owner}/{repo}/releases?per_page=3"
    token = os.getenv("GITHUB_TOKEN")
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"

    try:
        res = requests.get(url, headers=headers, timeout=12)
        if res.status_code == 200:
            return res.json()
        logger.warning(f"Failed to fetch {owner}/{repo}: HTTP {res.status_code}")
    except Exception as e:
        logger.error(f"Error connecting to GitHub for {owner}/{repo}: {e}")
    return []


def parse_breaking_changes_with_llm(package_name: str, ecosystem: str, release_tag: str, body_text: str) -> List[BreakingChange]:
    """Uses a low-cost LLM to extract deterministic syntax replacement mappings."""
    api_key = os.getenv("LLM_API_KEY")
    api_base = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
    model_name = os.getenv("LLM_MODEL", "gpt-4o-mini")

    if not api_key:
        return []

    system_prompt = (
        "You are an expert static analysis compiler. Analyze the provided software release notes. "
        "Extract ONLY breaking changes, deprecated methods, renamed arguments, and structural migrations. "
        "Strictly ignore bug fixes, performance improvements, and non-breaking additions. "
        "Output JSON only conforming to the schema: {\"changes\": [{\"package\": str, \"ecosystem\": str, "
        "\"version\": str, \"deprecated_symbol\": str, \"replacement_symbol\": str, \"change_type\": str, "
        "\"syntax_before\": str, \"syntax_after\": str, \"summary\": str}]}. "
        "If no breaking changes exist, return {\"changes\": []}."
    )

    user_prompt = f"Package: {package_name} ({ecosystem})\nRelease: {release_tag}\n\nChangelog:\n{body_text[:4000]}"

    try:
        res = requests.post(
            f"{api_base}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model_name,
                "temperature": 0.0,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            },
            timeout=30
        )
        data = res.json()
        content = json.loads(data["choices"][0]["message"]["content"])
        return [BreakingChange(**item) for item in content.get("changes", [])]
    except Exception as e:
        logger.error(f"LLM parsing failed for {package_name} {release_tag}: {e}")
        return []


def run():
    logger.info("Executing SDK Diff Wire...")
    all_changes = []

    for target in TARGET_REPOSITORIES:
        releases = fetch_github_releases(target["owner"], target["repo"])
        for rel in releases:
            tag = rel.get("tag_name", "unknown")
            body = rel.get("body", "")
            if not body or len(body.strip()) < 50:
                continue

            # Identify if release notes mention deprecation/breaking changes
            body_lower = body.lower()
            if any(k in body_lower for k in ["breaking", "deprecated", "removed", "migration"]):
                changes = parse_breaking_changes_with_llm(target["package"], target["ecosystem"], tag, body)
                all_changes.extend(changes)

    # Format machine-readable LLM digest
    md_lines = [
        "# Active SDK Breaking Changes & Deprecations",
        "> Anti-hallucination syntax ground-truth for AI coding agents.\n",
        "## Recent Deprecation Mappings"
    ]
    for c in all_changes:
        md_lines.extend([
            f"### [{c.ecosystem.upper()}] {c.package} (v{c.version})",
            f"- **Deprecated:** `{c.deprecated_symbol}`",
            f"- **Replacement:** `{c.replacement_symbol}`",
            f"- **Legacy Syntax:** `{c.syntax_before}`",
            f"- **Modern Syntax:** `{c.syntax_after}`",
            f"- **Reason:** {c.summary}\n"
        ])

    save_wire_data(
        domain="sdk_diff",
        payload_key="breaking_changes",
        items=[c.model_dump() for c in all_changes],
        markdown_brief="\n".join(md_lines)
    )
    logger.info(f"SDK Diff Wire published {len(all_changes)} breaking changes.")
