"""
Entity inference — extracts the subject entity_id from user text.

Extracted from prompts.py in withcare_agent_arch_codebase_v3.
Two-phase approach:
  1. Keyword matching (English + Chinese) — fast, no LLM call
  2. LLM fallback — if no keyword match and client is provided
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


async def infer_subject_entity(user_request: str, client: Any = None) -> str:
    """
    Best-effort inference for subject_entity_id when LLM omits it.

    Two-phase approach:
      1. Keyword matching (English + Chinese) — fast, no LLM call
      2. LLM fallback — if no keyword match and client is provided
    """
    text = user_request.lower()

    # ── English keywords ──
    # Check grandparent BEFORE mom/dad to avoid "grandmother" matching "mother"
    if "grandma" in text or "grandmother" in text or "grandpa" in text or "grandfather" in text:
        return "care_recipient:grandparent"
    if "my mom" in text or "mother" in text:
        return "care_recipient:mom"
    if "my dad" in text or "father" in text:
        return "care_recipient:dad"
    if "my spouse" in text or "husband" in text or "wife" in text:
        return "care_recipient:spouse"
    if "myself" in text or "my own" in text or " me " in text:
        return "user:self"

    # ── Chinese keywords ──
    # Mom / mother
    if any(kw in text for kw in ["我妈", "母亲", "妈妈", "我娘", "老母亲", "我老妈"]):
        return "care_recipient:mom"
    # Dad / father
    if any(kw in text for kw in ["我爸", "父亲", "爸爸", "我爹", "老父亲", "我老爸"]):
        return "care_recipient:dad"
    # Spouse
    if any(kw in text for kw in ["老公", "老婆", "配偶", "丈夫", "妻子", "爱人", "先生", "太太"]):
        return "care_recipient:spouse"
    # Grandparent
    if any(kw in text for kw in ["奶奶", "外婆", "爷爷", "外公", "姥姥", "姥爷", "祖母", "祖父"]):
        return "care_recipient:grandparent"
    # Self
    if any(kw in text for kw in ["我自己", "本人", "帮我"]):
        # "帮我" alone is ambiguous — could be "help me [with my mom]"
        # Only match if there's no other family keyword nearby
        pass

    # ── LLM fallback ──
    if client:
        try:
            llm_prompt = (
                "You are a subject-entity extractor for a caregiver assistant.\n"
                "Given the user's request, determine WHO the request is about.\n\n"
                f"User request: \"{user_request}\"\n\n"
                "Respond with EXACTLY ONE of these identifiers:\n"
                "- care_recipient:mom\n"
                "- care_recipient:dad\n"
                "- care_recipient:spouse\n"
                "- care_recipient:grandparent\n"
                "- user:self\n"
                "- care_recipient:unknown\n\n"
                "Output ONLY the identifier, nothing else."
            )
            response = await client.async_chat(prompt=llm_prompt, max_tokens=30, temperature=0.0)
            result = response.strip().lower()
            valid = {
                "care_recipient:mom", "care_recipient:dad",
                "care_recipient:spouse", "care_recipient:grandparent",
                "user:self", "care_recipient:unknown",
            }
            if result in valid:
                return result
        except Exception as e:
            logger.warning(f"LLM entity inference fallback failed: {e}")

    return "care_recipient:unknown"
