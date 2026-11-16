# Corrective Retrieval-Augmented Generation (CRAG)

Corrective Retrieval-Augmented Generation was proposed by Yan et al. in 2024 to make RAG robust when retrieval goes wrong. The key idea is to judge the quality of the retrieved documents before using them, and to trigger a different knowledge-gathering action depending on that judgement. CRAG is plug-and-play: it can be added on top of many existing RAG pipelines.

## Retrieval evaluator

In the original paper the retrieval evaluator is a lightweight T5-large model fine-tuned to output a relevance score for each (question, document) pair. Practical implementations often replace it with an LLM-as-judge prompt or a cross-encoder reranker. The scores of all retrieved documents are compared with two thresholds, an upper and a lower threshold.

## The three actions

- Correct: at least one retrieved document scores above the upper threshold. The system keeps the relevant documents, refines them, and generates from local knowledge.
- Incorrect: every retrieved document scores below the lower threshold. The retrieved documents are discarded and the system falls back to web search to find external knowledge.
- Ambiguous: the scores fall between the thresholds. The system cannot be sure, so it combines the refined internal documents with external knowledge from web search.

## Knowledge refinement (decompose-then-recompose)

Even a relevant document contains sentences that do not help. CRAG splits each document into small knowledge strips, scores each strip for relevance, filters out the irrelevant strips and recomposes the remaining ones. This keeps the generator's context short and focused.

## Web search and query rewriting

When web search is needed, the question is first rewritten into a keyword-style search query, because natural-language questions are often poor search queries. Search results are then refined in the same way as internal documents. Implementations frequently use a search API such as Tavily, which returns cleaned page content suited for LLMs.

## Results

The paper evaluated CRAG on PopQA (short-form QA), Biography (long-form generation), PubHealth (true-or-false claims) and ARC-Challenge (multiple-choice reasoning), showing improvements over standard RAG and over Self-RAG when CRAG was combined with it.

## Related work

Self-RAG (Asai et al., 2024) is a related self-reflective approach. REALM (Guu et al., 2020) and Fusion-in-Decoder (Izacard and Grave, 2021) are earlier retrieval-augmented models.
