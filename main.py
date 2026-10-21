#!/usr/bin/env python3
"""
Agent Intelligence Hub - Master Orchestrator
Executes all domain ingesters and builds the root llms.txt directory manifest.
"""

import logging
from datetime import datetime, timezone
from ingesters import ingest_sdk_diff, ingest_llm_economy

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("IntelWire.Master")

def generate_root_llms_txt():
    now_iso = datetime.now(timezone.utc).isoformat()
    content = f"""# Agent Intelligence Wire
> High-signal, machine-readable datasets engineered exclusively for autonomous AI agents, coding assistants, and dynamic routing engines.
> Last synchronized: {now_iso}

## Available Data Endpoints

### 1. SDK Diff & Deprecation Registry
Ground-truth breaking changes, deprecated syntax, and replacement methods extracted from official GitHub releases.
- [Canonical JSON](data/sdk_diff/today.json): Full machine-readable schema with syntax before/after mappings.
- [LLM Context Digest](data/sdk_diff/llms.txt): Token-efficient markdown table of recent breaking changes.
- Archive Path: `data/sdk_diff/archive/YYYY/MM/`

### 2. LLM Token Economy & Model Limits
Real-time pricing per 1M tokens (input/output), maximum context ceilings, and native function-calling flags across frontier and open-weights models.
- [Canonical JSON](data/llm_economy/today.json): Queryable model array for dynamic programmatic routing.
- [LLM Context Digest](data/llm_economy/llms.txt): Markdown table for quick zero-shot routing injection.
- Archive Path: `data/llm_economy/archive/YYYY/MM/`

## Agent Consumption Instructions
- **Coding Assistants (Cursor, Copilot, Devin):** Fetch `data/sdk_diff/today.json` prior to generating library-specific code to prevent using deprecated methods.
- **Router Agents (LangGraph, CrewAI):** Fetch `data/llm_economy/today.json` to calculate runtime token costs and select models that satisfy context window requirements.
"""
    with open("llms.txt", "w", encoding="utf-8") as f:
        f.write(content)
    logger.info("Master root llms.txt generated.")


def main():
    logger.info("Starting intelligence collection cycle...")

    for name, module in [
        ("SDK Diff Wire", ingest_sdk_diff),
        ("LLM Token Economy Wire", ingest_llm_economy)
    ]:
        try:
            logger.info(f"Running {name}...")
            module.run()
        except Exception as e:
            logger.error(f"Error executing {name}: {e}")

    generate_root_llms_txt()
    logger.info("Intelligence collection cycle completed.")


if __name__ == "__main__":
    main()
