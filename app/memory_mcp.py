"""
Memory MCP — K8s-deployable wrapper for Memory MCP tools.

This is a FastMCP sub-server that exposes memory tools for the WithCare
User Memory Framework. All memory infrastructure is self-contained in
the memory/ package — no external codebase dependencies.

Mounted into the main FastMCP server via main.py.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

from anthropic import Anthropic
from fastmcp import FastMCP

from memory.context_bundle import get_context_bundle, bundle_to_prompt_block
from memory.event_store import get_event_store
from memory.fact_store import get_fact_store
from memory.key_resolver import get_key_registry, get_key_resolver
from memory.memory_write_gate import (
    build_confirmation_questions,
    commit_updates,
    propose_updates,
)
from memory.models.fact_models import AliasRecord, ExtractedFact
from memory.entity_inference import infer_subject_entity
from memory.request_store import get_request_store

logger = logging.getLogger(__name__)

memory_mcp = FastMCP(name="memory-mcp")


# ─── Tool 1: Get Context Bundle ─────────────────────────────

@memory_mcp.tool(
    name="memory_get_context_bundle",
    description="Assemble a structured context bundle for the current conversation turn.",
)
async def memory_get_context_bundle(
    user_id: str,
    message: str = "",
    request_dict: Optional[dict] = None,
    k: int = 5,
) -> dict:
    bundle = await get_context_bundle(
        user_id=user_id, request_dict=request_dict, message=message, k=k,
    )
    result = bundle.model_dump(mode="json")
    result["prompt_block"] = bundle_to_prompt_block(bundle)
    return result


# ─── Tool 2: Get Profile Facts ──────────────────────────────

@memory_mcp.tool(
    name="memory_get_profile_facts",
    description="Get active facts for a specific entity.",
)
async def memory_get_profile_facts(
    user_id: str, entity_id: str, fact_keys: Optional[list[str]] = None,
) -> list[dict]:
    store = get_fact_store()
    facts = await store.get_active_facts(user_id, entity_id, fact_keys)
    return [f.model_dump(mode="json") for f in facts]


# ─── Tool 5: Resolve Fact Key ───────────────────────────────

@memory_mcp.tool(
    name="memory_resolve_fact_key",
    description="Map a natural-language fact description to a canonical FactKey.",
)
async def memory_resolve_fact_key(
    fact_text: str, entity_id: str, request_type: str = "unknown",
) -> dict:
    resolver = get_key_resolver()
    result = await resolver.resolve(
        fact_text=fact_text, entity_id=entity_id,
        context={"request_type": request_type},
    )
    return result.model_dump(mode="json")


# ─── Tool 6: Propose Updates ────────────────────────────────

@memory_mcp.tool(
    name="memory_propose_updates",
    description="Run the Memory Write Gate on extracted facts.",
)
async def memory_propose_updates(
    extracted_facts: list[dict], existing_fact_keys: Optional[list[str]] = None,
) -> dict:
    facts = [ExtractedFact(**f) for f in extracted_facts]
    if existing_fact_keys:
        existing_set = set(existing_fact_keys)
        facts = [f for f in facts if f.fact_key not in existing_set]
    proposal = propose_updates(facts)
    questions = build_confirmation_questions(proposal.needs_confirm)
    result = proposal.model_dump(mode="json")
    result["confirmation_questions"] = questions
    return result


# ─── Tool 7: Commit Updates ─────────────────────────────────

@memory_mcp.tool(
    name="memory_commit_updates",
    description="Write approved facts to the Fact Store.",
    tags={"write", "destructive"},
)
async def memory_commit_updates(
    user_id: str, request_id: str, facts_to_commit: list[dict],
    justification: str, actor: str = "agent", conflict_strategy: str = "auto",
) -> dict:
    facts = [ExtractedFact(**f) for f in facts_to_commit]
    committed = await commit_updates(
        user_id=user_id, request_id=request_id,
        facts_to_commit=facts, justification=justification,
        actor=actor, conflict_strategy=conflict_strategy,
    )
    return {
        "committed_count": len(committed),
        "committed_fact_ids": [f.fact_id for f in committed],
    }


# ─── Tool 8: Add Event ──────────────────────────────────────

@memory_mcp.tool(
    name="memory_add_event",
    description="Write an episodic event to the UserEventTable.",
)
async def memory_add_event(
    user_id: str, event_type: str, content: str,
    request_id: Optional[str] = None,
    care_recipient_id: Optional[str] = None,
    tags: Optional[list[str]] = None,
) -> dict:
    store = get_event_store()
    event = await store.add_event(
        user_id=user_id, event_type=event_type, content=content,
        request_id=request_id, care_recipient_id=care_recipient_id, tags=tags,
    )
    return {"event_id": event.event_id, "timestamp": event.timestamp.isoformat()}


# ─── Tool 9: Resolve Entity ID ──────────────────────────────

@memory_mcp.tool(
    name="memory_resolve_entity_id",
    description="Infer the subject entity_id from user text.",
)
async def memory_resolve_entity_id(
    user_text: str,
    known_entities: Optional[list[str]] = None,
    language_hint: Optional[str] = None,
) -> dict:
    entity_id = await infer_subject_entity(user_text, client=None)
    return {"entity_id": entity_id}


# ─── Tool 10: Batch Resolve Fact Keys ───────────────────────

@memory_mcp.tool(
    name="memory_resolve_fact_keys_batch",
    description="Batch resolve multiple fact descriptions to canonical FactKeys.",
)
async def memory_resolve_fact_keys_batch(
    facts: list[dict], entity_id: str, request_type: str = "unknown",
) -> list[dict]:
    resolver = get_key_resolver()
    results = await resolver.resolve_batch(
        facts=facts, entity_id=entity_id, context={"request_type": request_type},
    )
    return [r.model_dump(mode="json") for r in results]


# ─── Tool 11: Get Pending Confirmations ─────────────────────

@memory_mcp.tool(
    name="memory_get_pending_confirmations",
    description="Query memory_candidate events that need user confirmation.",
)
async def memory_get_pending_confirmations(
    user_id: str, entity_id: Optional[str] = None,
) -> list[dict]:
    store = get_event_store()
    events = await store.get_recent_events(
        user_id=user_id, event_types=["memory_candidate"], limit=20,
    )
    results = []
    for evt in events:
        structured = evt.structured or {}
        if entity_id and structured.get("entity_id") and structured["entity_id"] != entity_id:
            continue
        results.append({
            "event_id": evt.event_id,
            "fact_key": structured.get("fact_key", ""),
            "fact_label": structured.get("fact_label", ""),
            "value": structured.get("value"),
            "confidence": structured.get("confidence", 0.0),
            "evidence": structured.get("evidence", ""),
            "timestamp": evt.timestamp.isoformat(),
        })
    return results


# ─── Tool 12: Confirm Fact ──────────────────────────────────

@memory_mcp.tool(
    name="memory_confirm_fact",
    description="Promote or reject a candidate fact after user confirmation.",
    tags={"write"},
)
async def memory_confirm_fact(
    user_id: str, event_id: str, confirmed: bool,
    corrected_value: Optional[str] = None,
) -> dict:
    fact_store = get_fact_store()
    event_store = get_event_store()
    events = await event_store.get_recent_events(
        user_id=user_id, event_types=["memory_candidate"], limit=50,
    )
    target_event = None
    for evt in events:
        if evt.event_id == event_id:
            target_event = evt
            break
    if not target_event:
        return {"status": "error", "message": f"Event {event_id} not found"}

    structured = target_event.structured or {}
    fact_key = structured.get("fact_key", "")
    entity_id = structured.get("entity_id") or target_event.care_recipient_id or "care_recipient:unknown"
    value = corrected_value if corrected_value is not None else structured.get("value")

    if confirmed:
        record = await fact_store.upsert_fact(
            user_id=user_id, entity_id=entity_id, fact_key=fact_key,
            new_value=value, fact_label=structured.get("fact_label", ""),
            confidence=structured.get("confidence", 0.9),
            source_type=structured.get("source_type", "user"),
            evidence=structured.get("evidence", ""),
            verification_level="explicit_user_confirmed",
            conflict_strategy="overwrite",
        )
        return {"status": "confirmed", "fact_id": record.fact_id, "fact_key": fact_key}
    return {"status": "rejected", "fact_key": fact_key}


# ─── Tool 13: Write Back Aliases ────────────────────────────

@memory_mcp.tool(
    name="memory_write_back_aliases",
    description="Write alias mappings to the FactAliasTable.",
    tags={"write"},
)
async def memory_write_back_aliases(
    canonical_key: str, aliases: list[str], scope: str = "global",
) -> dict:
    store = get_fact_store()
    written = 0
    for alias_text in aliases:
        normalized = alias_text.strip().lower()
        if not normalized:
            continue
        alias = AliasRecord(
            normalized_alias=normalized, canonical_key=canonical_key,
            scope=scope, confidence=0.8, status="active",
        )
        await store.put_alias(alias)
        written += 1
    return {"written_count": written, "canonical_key": canonical_key}


# ─── Tool 14: Bind Facts (composite pipeline) ───────────────

@memory_mcp.tool(
    name="memory_bind_facts",
    description=(
        "Composite tool: extract facts from a summary, resolve keys, "
        "run write gate, and commit in one call. Returns slot_refs mapping "
        "of fact_key → fact_id for committed facts."
    ),
    tags={"write"},
)
async def memory_bind_facts(
    user_id: str,
    request_id: str,
    entity_id: str,
    request_type: str,
    updated_summary: str,
    extracted_facts: list[dict],
    existing_slot_refs: Optional[dict] = None,
) -> dict:
    """
    Full extract→resolve→propose→commit pipeline in one MCP call.

    Unlike the withcare slot_fact_binder, this tool expects pre-extracted
    facts (the LLM extraction step is done by the caller) so we don't
    need the full prompts.py machinery.

    Args:
        user_id: User identifier
        request_id: Current request ID
        entity_id: Subject entity (e.g. "care_recipient:mom")
        request_type: Request type from taxonomy
        updated_summary: The info_collection summary text
        extracted_facts: List of dicts with fact_key, fact_label, value, etc.
        existing_slot_refs: Already-committed slot refs to skip (dedup)

    Returns:
        slot_refs: {fact_key: fact_id} for committed facts
        needs_confirm: list of facts needing user confirmation
        committed_count: number of facts auto-committed
    """
    if not extracted_facts:
        return {"slot_refs": {}, "needs_confirm": [], "committed_count": 0}

    existing_keys = set((existing_slot_refs or {}).keys())

    # Step 1: Build ExtractedFact objects, filtering already-extracted keys
    pre_facts: List[ExtractedFact] = []
    for raw in extracted_facts:
        fk = raw.get("fact_key", "")
        if not fk or fk in existing_keys:
            continue
        pre_facts.append(ExtractedFact(
            entity_id=entity_id,
            fact_key=fk,
            fact_label=raw.get("fact_label", ""),
            value=raw.get("value"),
            value_type=raw.get("value_type", "string"),
            confidence=float(raw.get("confidence", 0.5)),
            source_type=raw.get("source_type", "user"),
            source_ref=request_id,
            evidence=raw.get("evidence", ""),
            explicit_user_confirmed=raw.get("explicit_user_confirmed", False),
        ))

    if not pre_facts:
        return {"slot_refs": {}, "needs_confirm": [], "committed_count": 0}

    # Step 2: Batch resolve keys (BM25-only in MCP context, no LLM client)
    resolver = get_key_resolver()
    try:
        batch_inputs = [
            {"fact_key": e.fact_key, "fact_label": e.fact_label, "evidence": e.evidence}
            for e in pre_facts
        ]
        batch_results = await resolver.resolve_batch(
            facts=batch_inputs,
            entity_id=entity_id,
            context={"request_type": request_type},
        )
        for extracted, result in zip(pre_facts, batch_results):
            if result.decision == "map" and result.canonical_key != "unknown":
                extracted.fact_key = result.canonical_key
            else:
                extracted.confidence = min(extracted.confidence, 0.65)
    except Exception as e:
        logger.warning(f"Batch key resolution failed in bind_facts: {e}, using raw keys")
        for extracted in pre_facts:
            extracted.confidence = min(extracted.confidence, 0.6)

    # Step 3: Write gate classification
    proposal = propose_updates(pre_facts)

    # Step 4: Commit auto_patch
    committed = []
    if proposal.auto_patch:
        committed = await commit_updates(
            user_id=user_id,
            request_id=request_id,
            facts_to_commit=proposal.auto_patch,
            justification=f"Auto-extracted from info_collection summary (request={request_id})",
            actor="memory_bind_facts",
        )

    # Step 5: Store needs_confirm as memory_candidate events
    if proposal.needs_confirm:
        event_store = get_event_store()
        for fact in proposal.needs_confirm:
            try:
                await event_store.add_event(
                    user_id=user_id,
                    event_type="memory_candidate",
                    content=f"Unconfirmed fact: {fact.fact_label or fact.fact_key} = {fact.value}",
                    request_id=request_id,
                    care_recipient_id=entity_id if entity_id.startswith("care_recipient:") else None,
                    structured={
                        "fact_key": fact.fact_key,
                        "fact_label": fact.fact_label,
                        "value": fact.value,
                        "confidence": fact.confidence,
                        "evidence": fact.evidence,
                        "source_type": fact.source_type,
                    },
                    tags=["needs_confirm", "slot_binding"],
                )
            except Exception as e:
                logger.warning(f"Failed to store memory candidate: {e}")

    # Step 6: Build slot_refs
    slot_refs: Dict[str, str] = {}
    for record in committed:
        slot_refs[record.fact_key] = record.fact_id

    # Build confirmation questions for needs_confirm
    confirm_questions = build_confirmation_questions(proposal.needs_confirm)

    logger.info(
        f"memory_bind_facts: {len(committed)} committed, "
        f"{len(proposal.needs_confirm)} need confirm, "
        f"{len(proposal.reject)} rejected"
    )

    return {
        "slot_refs": slot_refs,
        "committed_count": len(committed),
        "needs_confirm": confirm_questions,
        "rejected_count": len(proposal.reject),
    }


# ─── Tool 15: Get Requests by Status ─────────────────────────

@memory_mcp.tool(
    name="memory_get_requests_by_status",
    description=(
        "Query requests filtered by status. Use this when the user asks about "
        "in-progress, queued, blocked, completed, or created requests. "
        "Valid statuses: created, collecting, executing, paused, completed, cancelled. "
        "Returns summaries sorted by most recently touched first. "
        "Each summary includes: request_id, title, goal, status, request_type, "
        "subject_entity_id, priority, created_at, last_touched_at, summary_current, stage_detail."
    ),
)
async def memory_get_requests_by_status(
    user_id: str,
    status: str,
    limit: int = 20,
) -> list[dict]:
    store = get_request_store()
    return await store.query_by_status(user_id=user_id, status=status, limit=limit)


# ─── Tool 16: Get Requests by Entity ─────────────────────────

@memory_mcp.tool(
    name="memory_get_requests_by_entity",
    description=(
        "Query requests related to a specific care recipient or entity. "
        "Use this when the user asks 'How has mom been doing?' or 'What have we "
        "done for dad?'. The entity_id should be a canonical entity identifier "
        "like 'care_recipient:mom' or 'care_recipient:dad'. "
        "Optionally filter to requests after a given ISO date (e.g. '2025-12-01T00:00:00'). "
        "Returns summaries sorted by most recently touched first."
    ),
)
async def memory_get_requests_by_entity(
    entity_id: str,
    limit: int = 20,
    after_date: Optional[str] = None,
) -> list[dict]:
    store = get_request_store()
    return await store.query_by_entity(
        entity_id=entity_id, limit=limit, after_date=after_date,
    )


# ─── Tool 17: Get Request Detail ─────────────────────────────

@memory_mcp.tool(
    name="memory_get_request_detail",
    description=(
        "Get full detail for a single request by its request_id. "
        "Use this when the user asks for more information about a specific request, "
        "or when you need to inspect slots, open_questions, or artifacts. "
        "Returns the complete request record including payload, slots, "
        "open_questions, artifacts, prereq_gate, and audit trail."
    ),
)
async def memory_get_request_detail(
    user_id: str,
    request_id: str,
) -> dict:
    store = get_request_store()
    result = await store.get_request(user_id=user_id, request_id=request_id)
    if result is None:
        return {"error": "not_found", "message": f"Request {request_id} not found"}
    return result


# ─── Tool 18: List Recent Requests ───────────────────────────

@memory_mcp.tool(
    name="memory_list_recent_requests",
    description=(
        "List recent requests for a user, optionally filtered to a date range. "
        "Use this when the user asks 'What did you help me with last month?' or "
        "'Show me my recent requests'. Pass after_date as an ISO timestamp "
        "(e.g. '2025-12-01T00:00:00') to filter by creation date. "
        "Returns summaries sorted by most recent first."
    ),
)
async def memory_list_recent_requests(
    user_id: str,
    limit: int = 20,
    after_date: Optional[str] = None,
) -> list[dict]:
    store = get_request_store()
    return await store.query_recent(
        user_id=user_id, limit=limit, after_date=after_date,
    )


# ═══════════════════════════════════════════════════════════════
# Change 1: Schema Resource
# ═══════════════════════════════════════════════════════════════

_WITHCARE_SCHEMA = """\
# WithCare DynamoDB Table Schemas

## WithCare_UserRequestTable
- **PK**: `USER#{user_id}`
- **SK**: `REQ#{created_at}#{request_id}`
- **GSI1** (by status): PK=`USER#{user_id}#STATUS#{status}`, SK=`LAST#{timestamp}#REQ#{request_id}`
- **GSI2** (by entity): PK=`RECIPIENT#{entity_id}`, SK=`LAST#{timestamp}#REQ#{request_id}`
- **Fields**: request_id, title, goal, status, request_type, subject_entity_id, priority, created_at, last_touched_at, summary_current, stage_detail, name, target
- **Valid statuses**: created, collecting, executing, paused, completed, cancelled

## WithCare_UserFactTable
- **PK**: `USER#{user_id}#ENT#{entity_id}`
- **SK**: `FACT#{fact_key}#TS#{timestamp}#{fact_id}`
- **GSI1**: by entity+key+status
- **GSI2**: all active facts for user (scan with filter)
- **Fields**: fact_id, user_id, entity_id, fact_key, fact_label, value, value_type, status, confidence, verification_level, source_type, source_ref, evidence, created_at, updated_at

## WithCare_UserEventTable
- **PK**: `USER#{user_id}`
- **SK**: `EVT#{timestamp}#{event_id}`
- **Fields**: event_id, user_id, event_type, content, request_id, care_recipient_id, structured, tags, timestamp, ttl
- **Event types**: dialogue_summary, tool_result, escalation, decision, memory_candidate, error

## WithCare_UserConversationTable
- **PK**: `CONV#{conversation_id}`
- **SK**: `MSG#{timestamp}#{message_id}`
- **GSI1**: PK=`USER#{user_id}#DATE#{YYYY-MM-DD}`, SK=`MSG#{timestamp}#{message_id}`

## Entity ID Format
- `care_recipient:mom`, `care_recipient:dad`, `care_recipient:grandparent`, `care_recipient:spouse`
- `user:self`
- Custom entities follow same pattern: `care_recipient:{label}`

## Available Query Methods

### requests table
- `query_recent(limit, after_date?)` — recent requests, optionally filtered by ISO date
- `query_by_entity(entity_id, limit, after_date?)` — requests for a care recipient
- `query_by_status(status, limit)` — requests filtered by status
- `get_request(request_id)` — single request full detail

### facts table
- `get_active_facts(entity_id, fact_keys?)` — active facts for an entity
- `get_user_entities()` — all distinct entity_ids with active facts for the user
- `get_all_active_facts_for_user()` — all active facts across all entities

### events table
- `get_recent_events(limit, event_types?)` — recent events, optionally filtered by type
- `get_events_for_request(request_id, limit)` — events for a specific request
"""


@memory_mcp.resource("schema://withcare-tables")
def withcare_table_schemas() -> str:
    """Return comprehensive DynamoDB schema documentation for all WithCare tables."""
    return _WITHCARE_SCHEMA


# ═══════════════════════════════════════════════════════════════
# Change 2: Query Planner Tool
# ═══════════════════════════════════════════════════════════════

_QUERY_PLANNER_SYSTEM = """\
You are a query planner for a caregiving platform's DynamoDB memory system.
Given a user's natural-language question and the database schema, generate a structured query plan.

SCHEMA:
{schema}

RULES:
1. Entity resolution: "my mom" → care_recipient:mom, "my dad" → care_recipient:dad, \
"my grandmother/grandma/grandfather/grandpa" → care_recipient:grandparent, \
"my spouse/husband/wife" → care_recipient:spouse, "myself/me" → user:self
2. Date extraction: "last January" → after_date=YYYY-01-01T00:00:00, "last month" → compute relative date, \
"last year" → after_date=(current_year-1)-01-01T00:00:00
3. Use the most specific method available. Prefer query_by_entity over query_recent when an entity is mentioned.
4. Generate 1-3 steps. Each step is a query against one table.
5. For comparison questions ("compare now vs last year"), use multiple steps with different date ranges.
6. Set needs_followup=true ONLY if you expect the first batch of results to be insufficient and a second round \
of queries would be needed (e.g., you need IDs from the first result to query details).

OUTPUT FORMAT (strict JSON, no markdown):
{{
  "reasoning": "brief explanation of your plan",
  "needs_followup": false,
  "steps": [
    {{
      "step_id": 1,
      "description": "human-readable description",
      "table": "requests|facts|events",
      "method": "method_name",
      "params": {{...}}
    }}
  ]
}}
"""


@memory_mcp.tool(
    name="memory_query_planner",
    description=(
        "LLM-driven query planner: given a user's natural-language question about their "
        "care history, generates a structured query plan (1-3 steps) specifying which "
        "tables and methods to call. Use this instead of manually choosing query tools "
        "when the user's question is complex or ambiguous."
    ),
)
async def memory_query_planner(
    user_question: str,
    user_id: str,
    known_entity_ids: list[str] = [],
    previous_results_summary: str = "",
) -> dict:
    """Generate a structured query plan from a natural-language question."""
    anthropic_client = Anthropic()

    entity_context = ""
    if known_entity_ids:
        entity_context = f"\nKnown entities for this user: {', '.join(known_entity_ids)}"

    previous_context = ""
    if previous_results_summary:
        previous_context = (
            f"\n\nPREVIOUS RESULTS (from earlier query round):\n{previous_results_summary}"
            "\nGenerate additional queries to fill gaps, or return empty steps if sufficient."
        )

    user_prompt = (
        f"User question: {user_question}\n"
        f"User ID: {user_id}"
        f"{entity_context}"
        f"{previous_context}"
        "\n\nGenerate the query plan as JSON."
    )

    try:
        response = anthropic_client.messages.create(
            model=os.environ.get("PLANNER_MODEL", "claude-sonnet-4-20250514"),
            max_tokens=1024,
            system=_QUERY_PLANNER_SYSTEM.format(schema=_WITHCARE_SCHEMA),
            messages=[{"role": "user", "content": user_prompt}],
        )

        text = response.content[0].text.strip()
        # Strip markdown fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3].strip()

        plan = json.loads(text)
        return plan

    except json.JSONDecodeError as e:
        logger.error(f"Query planner returned invalid JSON: {e}")
        return {"reasoning": "planner_json_error", "steps": [], "needs_followup": False}
    except Exception as e:
        logger.error(f"Query planner failed: {e}")
        return {"reasoning": f"planner_error: {e}", "steps": [], "needs_followup": False}


# ═══════════════════════════════════════════════════════════════
# Change 3: Query Executor Tool
# ═══════════════════════════════════════════════════════════════

@memory_mcp.tool(
    name="memory_execute_query",
    description=(
        "Execute a single structured query against any WithCare DynamoDB table. "
        "Typically called with steps from memory_query_planner. "
        "Specify the table (requests/facts/events), method name, and params dict."
    ),
)
async def memory_execute_query(
    user_id: str,
    table: str,
    method: str,
    params: dict,
) -> dict:
    """Generic query executor that dispatches to the appropriate store method."""
    request_store = get_request_store()
    fact_store = get_fact_store()
    event_store = get_event_store()

    dispatch = {
        ("requests", "query_recent"): lambda p: request_store.query_recent(user_id=user_id, **p),
        ("requests", "query_by_entity"): lambda p: request_store.query_by_entity(user_id=user_id, **p),
        ("requests", "query_by_status"): lambda p: request_store.query_by_status(user_id=user_id, **p),
        ("requests", "get_request"): lambda p: request_store.get_request(user_id=user_id, **p),
        ("facts", "get_active_facts"): lambda p: fact_store.get_active_facts(user_id=user_id, **p),
        ("facts", "get_user_entities"): lambda p: fact_store.get_user_entities(user_id=user_id),
        ("facts", "get_all_active_facts_for_user"): lambda p: fact_store.get_all_active_facts_for_user(user_id=user_id),
        ("events", "get_recent_events"): lambda p: event_store.get_recent_events(user_id=user_id, **p),
        ("events", "get_events_for_request"): lambda p: event_store.get_events_for_request(user_id=user_id, **p),
    }

    handler = dispatch.get((table, method))
    if handler is None:
        return {
            "error": "unknown_dispatch",
            "message": f"Unknown table/method combination: {table}/{method}",
            "valid_combinations": [f"{t}/{m}" for t, m in dispatch.keys()],
        }

    try:
        result = await handler(params)

        # Normalize result to a list of dicts for consistent output
        if result is None:
            items = []
        elif isinstance(result, list):
            items = [
                r.model_dump(mode="json") if hasattr(r, "model_dump") else r
                for r in result
            ]
        elif isinstance(result, dict):
            items = [result]
        else:
            items = [{"value": str(result)}]

        return {
            "table": table,
            "method": method,
            "result_count": len(items),
            "results": items,
        }

    except Exception as e:
        logger.error(f"memory_execute_query failed ({table}/{method}): {e}")
        return {
            "error": "execution_failed",
            "table": table,
            "method": method,
            "message": str(e),
        }


# ═══════════════════════════════════════════════════════════════
# Change 4: Query Strategy Prompt
# ═══════════════════════════════════════════════════════════════

@memory_mcp.prompt(name="withcare_query_strategy")
def withcare_query_strategy(user_question: str) -> str:
    """Teach the LLM how to decompose complex memory questions into query steps."""
    return f"""\
You need to answer the following user question using the WithCare memory system:

"{user_question}"

## Query Strategy Guide

### Entity Resolution
- "my mom/mother" → entity_id = care_recipient:mom
- "my dad/father" → entity_id = care_recipient:dad
- "my grandma/grandmother/grandpa/grandfather" → entity_id = care_recipient:grandparent
- "my spouse/husband/wife" → entity_id = care_recipient:spouse
- "myself/me/my own" → entity_id = user:self

### Date Range Extraction
- "last January" → after_date = (current_year - 1 if current month <= January else current_year)-01-01T00:00:00
- "last month" → compute ISO date for first day of previous month
- "last year" → after_date = (current_year - 1)-01-01T00:00:00
- "recently" or "latest" → no date filter, just use limit

### Choosing the Right Table & Method
1. **User asks about requests/tasks/what they did**: Use `requests` table
   - For a specific person: `query_by_entity` with entity_id
   - For a status filter: `query_by_status` with status
   - For general recent: `query_recent` with optional after_date
   - For a specific request detail: `get_request` with request_id

2. **User asks about a person's profile/condition/situation**: Use `facts` table
   - For one entity: `get_active_facts` with entity_id
   - For all entities: `get_all_active_facts_for_user`

3. **User asks about what happened during a request**: Use `events` table
   - For a specific request: `get_events_for_request` with request_id
   - For recent activity: `get_recent_events` with optional event_types filter

### Multi-Table Queries
- "How is mom doing?" → facts/get_active_facts + requests/query_by_entity (2 steps)
- "Compare mom's situation now vs last year" → facts/get_active_facts + requests/query_by_entity (recent) + requests/query_by_entity (last year) (3 steps)
- "What requests have I made for my mom?" → requests/query_by_entity (1 step)

### When to Use Follow-Up Rounds
- When you need a request_id from results to fetch events or details
- When initial results are empty and you want to broaden the search
- NOT needed for straightforward single-table queries

Use memory_query_planner to generate the plan, then memory_execute_query to run each step.
"""
