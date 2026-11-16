# Hallucination in large language models

A hallucination is output from a language model that is fluent and confident but not supported by facts or by the provided source material.

## Types

- Intrinsic hallucination: the output contradicts the source context, for example changing a date that appears in the retrieved document.
- Extrinsic hallucination: the output adds information that cannot be verified from the source, such as invented citations or statistics.

## Why language models hallucinate

Language models are trained to predict plausible next tokens, not to check facts. Their knowledge is frozen at training time, so they may produce outdated answers. They have no built-in signal for "I do not know", and gaps in the training data are filled with plausible-sounding text. In RAG systems, irrelevant or misleading retrieved passages are an additional cause, because the model tends to trust whatever is placed in its context.

## Mitigation techniques

- Retrieval-augmented generation grounds answers in documents and allows citations.
- Retrieval evaluation (as in Corrective RAG) filters out irrelevant context before generation.
- Instructing the model to answer only from the context and to say when information is missing.
- Answer validation: a second pass checks whether every claim is supported by the context (a faithfulness check) and triggers regeneration if not.
- Self-consistency: sampling several answers and keeping the one most answers agree on.
- Lower temperature decoding for factual tasks.

## Measuring hallucination

Hallucination rate is commonly reported as the fraction of answers containing at least one unsupported claim. Faithfulness scores from LLM judges or natural-language-inference models are used to estimate it automatically.
