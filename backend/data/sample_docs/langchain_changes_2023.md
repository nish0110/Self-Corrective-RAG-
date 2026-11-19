# LangChain Notes (written in 2023, outdated)

As of mid 2023 the standard way to build a chain in LangChain is the LLMChain class together with a PromptTemplate.

Retrieval question answering uses RetrievalQA.from_chain_type. Agents are created with initialize_agent. The latest stable version is 0.0.200.

All integrations live in the single langchain package.
