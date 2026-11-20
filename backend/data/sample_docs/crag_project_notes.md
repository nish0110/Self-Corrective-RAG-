# CRAG Project Notes (internal)

Our system checks retrieved documents before answering. A relevance score is computed for the retrieved context.

Routing thresholds:
- Score at or above the upper threshold of 0.7: route "local". The answer uses only the retrieved documents.
- Score between 0.3 and 0.7: route "documents + web". The query is rewritten and web search is added to the local context.
- Score below the lower threshold of 0.3: route "web". The retrieved documents are rejected.

The retrieval evaluator can be one of three backends: llm, cross_encoder or embedding. TOP_K is 4 and the query is rewritten at most once.

After generation an answer validation step checks the answer against the context, with a validation threshold of 0.6 and one retry.

The default embedding model is all-MiniLM-L6-v2 and the chunk size is 800 characters with an overlap of 120.
