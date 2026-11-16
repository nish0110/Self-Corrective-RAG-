# Vector databases and similarity search

A vector database stores high-dimensional embedding vectors and retrieves the vectors closest to a query vector. It is the retrieval engine of most RAG systems.

## Embeddings and similarity

An embedding model maps text to a fixed-length vector so that texts with similar meaning are close together. all-MiniLM-L6-v2, for example, produces 384-dimensional vectors. Closeness is usually measured with cosine similarity, which compares the angle between two vectors, or with dot product and Euclidean (L2) distance. When vectors are normalised to unit length, cosine similarity and dot product give the same ranking.

## Exact vs approximate search

Exact (brute-force) search compares the query with every stored vector. It is accurate but becomes slow for millions of vectors. Approximate Nearest Neighbour (ANN) algorithms trade a little accuracy for large speed-ups.

## HNSW

Hierarchical Navigable Small World (HNSW) is a graph-based ANN algorithm. It builds several layers of proximity graphs: the top layers are sparse and allow long jumps across the dataset, the bottom layer contains every vector. A search starts at the top layer, greedily moves towards the query, and descends layer by layer, which gives roughly logarithmic search time. Its main parameters are M (number of links per node) and ef (size of the candidate list during search).

## IVF

Inverted File indexes (IVF) cluster the vectors with k-means. At query time only the vectors in the few clusters nearest to the query are searched. The parameter nprobe controls how many clusters are visited.

## FAISS and ChromaDB

FAISS is a library from Meta for efficient similarity search on CPUs and GPUs; it provides flat, IVF and HNSW indexes and more. ChromaDB is an open-source embedding database aimed at LLM applications: it stores documents, metadata and embeddings together, persists to disk and uses HNSW internally. Metadata filters (for example source = "handbook.pdf") can be combined with similarity search.

## Chunking strategy

Retrieval quality depends heavily on chunking. Chunks that are too large dilute the embedding with unrelated content; chunks that are too small lose context. A recursive splitter that cuts on headings, then paragraphs, then sentences, with a small overlap between consecutive chunks, is a common default.
