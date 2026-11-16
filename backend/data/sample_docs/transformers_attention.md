# Transformers and the attention mechanism

The Transformer architecture was introduced by Vaswani et al. in 2017 in the paper "Attention Is All You Need". It replaced recurrence with attention and is the basis of modern large language models, vision transformers and the text encoders used in diffusion models.

## Scaled dot-product attention

Each token is projected into a query vector, a key vector and a value vector. The attention weights are computed as the softmax of the dot products between queries and keys, divided by the square root of the key dimension. The output for each token is the weighted sum of the value vectors. The scaling by the square root of the dimension keeps the dot products from growing too large and pushing the softmax into regions with tiny gradients.

## Multi-head attention

Instead of one attention operation, the model runs several attention heads in parallel, each with its own learned projections. Different heads can focus on different relationships, such as syntax or long-range references. Their outputs are concatenated and projected back to the model dimension.

## Positional information

Attention by itself ignores word order, so positional information is added. The original Transformer used fixed sinusoidal positional encodings; later models use learned position embeddings or rotary position embeddings (RoPE).

## Encoder and decoder

The original model has an encoder stack and a decoder stack. Each layer contains attention and a position-wise feed-forward network, with residual connections and layer normalisation. Encoder-only models such as BERT are used for understanding and embeddings; decoder-only models such as GPT generate text one token at a time using causal (masked) self-attention; encoder-decoder models such as T5 are used for sequence-to-sequence tasks.

## Cost

Self-attention compares every token with every other token, so its time and memory cost grow quadratically with sequence length. This is why long-context models use techniques such as efficient attention kernels and why RAG systems keep the retrieved context short.
