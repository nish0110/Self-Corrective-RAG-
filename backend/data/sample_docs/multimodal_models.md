# Multimodal models: connecting images and text

Multimodal models process more than one type of data, most commonly images and text. They power image search by text, image captioning, visual question answering and text-to-image generation.

## CLIP

CLIP (Contrastive Language-Image Pre-training, Radford et al., 2021) learns a shared embedding space for images and text. It has two encoders: an image encoder (a ResNet or a Vision Transformer) and a text encoder (a Transformer). CLIP was trained on about 400 million image-caption pairs collected from the internet.

Training uses a contrastive objective. In each batch of N image-text pairs, the model computes the similarity between every image and every caption. It is trained to give high similarity to the N correct pairs and low similarity to the N² − N incorrect pairs, using a symmetric cross-entropy loss over the similarity matrix.

Because images and text live in the same space, CLIP can do zero-shot classification: the class names are turned into prompts such as "a photo of a dog", embedded, and the image is assigned to the most similar prompt, without any task-specific training.

## Vision-language models

Vision-language models connect a vision encoder to a large language model, usually through a projection layer, so that the language model can read image features as if they were tokens. This allows the model to describe images, answer questions about them and follow multimodal instructions.

## Text-to-image generation

Text-to-image systems combine a text encoder with an image generator. In latent diffusion systems the text encoder (for example a CLIP text encoder or a T5 encoder) produces embeddings that condition the denoising network through cross-attention. Guidance techniques such as classifier-free guidance control how strictly the image follows the text.

## Multimodal RAG

Multimodal retrieval-augmented generation extends RAG to images, tables and diagrams. Images can be embedded with a model like CLIP and stored in the same vector database as text, or converted to text descriptions by a vision-language model before indexing. At query time both text and image evidence can be retrieved and passed to a multimodal model.
