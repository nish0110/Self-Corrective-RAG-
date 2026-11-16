# Retrieval-Augmented Generation (RAG) fundamentals

Retrieval-Augmented Generation combines a retriever with a text generator. Instead of relying only on the knowledge stored in a language model's parameters, a RAG system first fetches relevant passages from an external collection and then asks the model to answer using those passages. The idea was popularised by Lewis et al. (2020), who paired a dense passage retriever with a sequence-to-sequence generator for knowledge-intensive NLP tasks.

## Components of a RAG pipeline

1. Document ingestion: source files (PDFs, web pages, notes) are loaded and cleaned.
2. Chunking: long documents are split into smaller overlapping chunks, typically a few hundred to a thousand characters, so that each chunk covers one idea.
3. Embedding: every chunk is converted into a dense vector by an embedding model such as all-MiniLM-L6-v2.
4. Vector database: the vectors are stored in an index (for example FAISS or ChromaDB) that supports fast nearest-neighbour search.
5. Retrieval: the user's question is embedded with the same model and the top-k most similar chunks are returned.
6. Generation: the retrieved chunks are inserted into the prompt and a large language model writes the answer, ideally citing the chunks.

## Why RAG helps

RAG lets a system use private or recent documents without retraining the model, makes answers traceable to sources, and reduces (but does not remove) hallucination. Updating knowledge is as simple as adding documents to the index.

## Limitations of traditional RAG

Traditional RAG assumes that whatever the retriever returns is relevant. In practice retrieval fails in several ways:

- Irrelevant retrieval: chunks that are semantically similar to the question but do not contain the answer.
- Missing knowledge: the answer is simply not in the collection, yet the top-k chunks are still passed to the model.
- Outdated knowledge: the collection contains an older version of a fact.
- No quality check: the pipeline never measures whether retrieval succeeded, so the generator may produce a confident but wrong answer.

These weaknesses motivate corrective approaches such as Corrective RAG (CRAG), which evaluate retrieval quality before generation and take a corrective action when retrieval is poor.

## Common evaluation metrics

Retrieval quality is measured with precision@k, recall@k, Mean Reciprocal Rank (MRR) and hit rate (top-k accuracy). Generation quality is measured with faithfulness (is every claim supported by the context?), answer relevance (does the answer address the question?) and context relevance (is the retrieved context useful?). System metrics include latency, number of LLM calls and token usage.
