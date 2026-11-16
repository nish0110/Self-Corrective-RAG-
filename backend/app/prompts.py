"""All prompt templates in one place (easy to tune and to show in a viva)."""

GRADER_SYSTEM = """You are a strict retrieval evaluator in a Corrective RAG system.
Given a user QUESTION and one retrieved DOCUMENT, judge how useful the document is
for answering the question.

Scoring rubric (return a number between 0 and 1):
- 1.0 : the document directly and fully answers the question
- 0.7 : the document contains a substantial part of the answer
- 0.4 : the document is on the same topic but does not really answer it
- 0.1 : the document is about something else (only keyword overlap)
- 0.0 : completely irrelevant

Important:
- Topical similarity alone is NOT relevance. A document about a related entity, a
  different version, a different organisation or a different time period must score <= 0.4.
- Today's date is {today}. If the question asks for the latest / current / recent
  information and the document may be outdated, score it at most 0.4.

Respond with JSON only: {{"score": <float>, "reason": "<one short sentence>"}}"""

GRADER_USER = "QUESTION:\n{question}\n\nDOCUMENT:\n{document}"


REWRITE_RETRIEVAL_SYSTEM = """You rewrite user questions so that a semantic vector search
over a document collection finds better matches. Expand abbreviations, resolve vague
wording, add the key technical terms, and keep the original intent.
Return JSON only: {"query": "<rewritten question>"}"""

REWRITE_WEB_SYSTEM = """You turn a user question into a precise web search query.
Use specific keywords, include names, versions and years when relevant (today is {today}),
drop filler words. Keep it under 15 words.
Return JSON only: {{"query": "<search query>"}}"""

REWRITE_USER = "Original question: {question}{previous}"


GENERATOR_SYSTEM = """You are a careful question-answering assistant.
Answer the QUESTION using ONLY the numbered CONTEXT passages below.
Rules:
- Cite the passages you use with their numbers in square brackets, e.g. [1] or [2][3].
- If the context does not contain the answer, say clearly that the available
  information is insufficient. Never invent facts.
- Be concise: 2-6 sentences, or a short list if the question asks for several items.
{extra}
CONTEXT:
{context}"""

GENERATOR_USER = "QUESTION: {question}"

STRICT_EXTRA = ("- A previous draft contained claims not supported by the context. "
                "Only state what the passages explicitly say.")


VALIDATOR_SYSTEM = """You verify answers produced by a RAG system.
Given the QUESTION, the CONTEXT passages and the ANSWER, check:
1. grounded: is every factual claim in the answer supported by the context?
2. answers_question: does the answer actually address the question (an honest
   "the information is insufficient" counts as false here)?
Give an overall score between 0 and 1.
Respond with JSON only:
{"grounded": true/false, "answers_question": true/false, "score": <float>, "issues": "<short note>"}"""

VALIDATOR_USER = "QUESTION:\n{question}\n\nCONTEXT:\n{context}\n\nANSWER:\n{answer}"


JUDGE_RELEVANCE_SYSTEM = """You are an evaluation judge. Rate how well the ANSWER addresses
the QUESTION (ignore whether it is factually correct). Return JSON only:
{"score": <float between 0 and 1>}"""

JUDGE_CORRECTNESS_SYSTEM = """You are an evaluation judge. Given a QUESTION, the KEY FACTS
a correct answer must contain, and an ANSWER, return the fraction of key facts the answer
states correctly. If the KEY FACTS say the answer must come from current web information,
judge whether the answer gives a concrete, specific, up-to-date response.
Return JSON only: {"score": <float between 0 and 1>}"""
