"""Thin wrapper around the Anthropic SDK for the two AI features:

1. answer_question  -> "ask the server anything" (memory)
2. moderate_message -> smart content flagging (moderation)
"""

import json

import anthropic

import config

_client = anthropic.AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)


# --------------------------------------------------------------------------- #
# Memory: answer questions from server history
# --------------------------------------------------------------------------- #

ANSWER_SYSTEM = (
    "You are a helpful Discord server assistant with access to the server's "
    "message history. Answer the user's question using ONLY the provided "
    "message excerpts. Cite the channel and author when it's useful. If the "
    "excerpts don't contain the answer, say you couldn't find anything about "
    "it in the server's history rather than guessing. Be concise — this is a "
    "chat reply, not an essay."
)


async def answer_question(question: str, context_rows) -> str:
    if context_rows:
        context = "\n".join(
            f"[#{channel_name}] {author_name}: {content}"
            for channel_name, author_name, content, _created_at in context_rows
        )
    else:
        context = "(no relevant messages found)"

    user_content = (
        f"Server message excerpts:\n{context}\n\nQuestion: {question}"
    )

    response = await _client.messages.create(
        model=config.ANSWER_MODEL,
        max_tokens=2048,
        thinking={"type": "adaptive"},
        system=ANSWER_SYSTEM,
        messages=[{"role": "user", "content": user_content}],
    )
    return "".join(
        block.text for block in response.content if block.type == "text"
    ).strip()


# --------------------------------------------------------------------------- #
# Moderation: classify a message
# --------------------------------------------------------------------------- #

MOD_SYSTEM = (
    "You are a content-moderation classifier for a Discord server. Decide "
    "whether a message genuinely violates community guidelines: harassment, "
    "hate speech, credible threats, sexual content involving minors, "
    "spam/scams, or severe targeted toxicity. Be precise and conservative — "
    "do NOT flag ordinary profanity, dark humor, sarcasm, or heated but civil "
    "disagreement. Only flag content a human moderator would actually want to "
    "review. Always keep a human in the loop; never assume your judgment is "
    "final."
)

MOD_SCHEMA = {
    "type": "object",
    "properties": {
        "flagged": {"type": "boolean"},
        "category": {
            "type": "string",
            "enum": [
                "harassment",
                "hate",
                "threat",
                "csam",
                "spam_scam",
                "toxicity",
                "none",
            ],
        },
        "severity": {
            "type": "string",
            "enum": ["none", "low", "medium", "high"],
        },
        "reason": {"type": "string"},
    },
    "required": ["flagged", "category", "severity", "reason"],
    "additionalProperties": False,
}


async def moderate_message(content: str) -> dict:
    response = await _client.messages.create(
        model=config.MODERATION_MODEL,
        max_tokens=512,
        system=MOD_SYSTEM,
        messages=[{"role": "user", "content": f"Message to evaluate:\n{content}"}],
        output_config={"format": {"type": "json_schema", "schema": MOD_SCHEMA}},
    )
    text = next(
        (block.text for block in response.content if block.type == "text"), "{}"
    )
    return json.loads(text)
