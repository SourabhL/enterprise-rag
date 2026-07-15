import re
from dataclasses import dataclass

from app.logging_config import get_logger
from app.providers.base import LLMProvider, Message

logger = get_logger(__name__)

_SCORE_PATTERN = re.compile(r"SCORE:\s*(\d)")

_GROUNDEDNESS_SYSTEM = (
    "You are grading whether an AI-generated answer is grounded in the provided "
    "context -- i.e. every claim in the answer traces back to something the "
    "context actually says, with no fabrication. Score 1 (not grounded) to 5 "
    "(fully grounded). Respond with a line 'SCORE: <1-5>' followed by a one-"
    "sentence rationale."
)

_RELEVANCE_SYSTEM = (
    "You are grading whether an AI-generated answer addresses the user's "
    "question. Score 1 (irrelevant) to 5 (directly and completely addresses the "
    "question). Respond with a line 'SCORE: <1-5>' followed by a one-sentence "
    "rationale."
)


@dataclass(frozen=True)
class JudgeScore:
    score: int
    rationale: str


async def _judge(llm_provider: LLMProvider, system: str, user: str) -> JudgeScore:
    response = await llm_provider.generate(
        system=system,
        messages=[Message(role="user", content=user)],
        max_tokens=300,
        effort="low",
    )
    match = _SCORE_PATTERN.search(response.text)
    if match is None:
        logger.warning("judge_score_unparseable", response_text=response.text[:500])
        return JudgeScore(score=0, rationale=f"[unparseable judge response] {response.text}")
    return JudgeScore(score=int(match.group(1)), rationale=response.text)


async def score_groundedness(
    llm_provider: LLMProvider, *, question: str, answer: str, context: str
) -> JudgeScore:
    user = f"Context:\n{context}\n\nQuestion: {question}\n\nAnswer: {answer}"
    return await _judge(llm_provider, _GROUNDEDNESS_SYSTEM, user)


async def score_relevance(llm_provider: LLMProvider, *, question: str, answer: str) -> JudgeScore:
    user = f"Question: {question}\n\nAnswer: {answer}"
    return await _judge(llm_provider, _RELEVANCE_SYSTEM, user)
