# Diffusion models for image generation

Diffusion models are generative models that learn to create data by reversing a gradual noising process. They are behind most modern text-to-image systems and have largely replaced GANs for high-quality image synthesis.

## Forward process

In Denoising Diffusion Probabilistic Models (DDPM, Ho et al., 2020) the forward process takes a clean image and adds a small amount of Gaussian noise at each of T steps (T = 1000 in the original paper). The amount of noise added at each step is controlled by a variance schedule. After enough steps the image becomes indistinguishable from pure Gaussian noise. Because the noise is Gaussian, a noisy image at any step t can be sampled directly from the clean image in closed form, which makes training efficient.

## Reverse process

The reverse process starts from random noise and removes noise step by step to produce an image. A neural network, usually a U-Net with attention layers, is trained to predict the noise that was added to an image at a given step. Training uses a simple mean-squared-error loss between the true noise and the predicted noise. At generation time the network's prediction is used to take one denoising step at a time from step T back to step 0.

## Noise schedules

The original DDPM used a linear variance schedule. Nichol and Dhariwal (2021) proposed a cosine schedule that destroys information more slowly and improves sample quality, especially at lower resolutions.

## Faster sampling

Running 1000 denoising steps is slow. DDIM (Song et al., 2020) defines a non-Markovian sampling process that produces good images in far fewer steps, for example 50, without retraining the model.

## Latent diffusion and Stable Diffusion

Latent Diffusion Models (Rombach et al., 2022) run the diffusion process in the compressed latent space of a variational autoencoder instead of in pixel space. This greatly reduces compute cost. Text conditioning is added through cross-attention layers that attend to embeddings from a text encoder. Stable Diffusion is based on this design.

## Classifier-free guidance

Classifier-free guidance (Ho and Salimans, 2022) trains one model both with and without the conditioning (for example the text prompt), by randomly dropping the condition during training. At sampling time the conditional and unconditional noise predictions are combined, with a guidance scale that pushes samples to follow the prompt more closely at the cost of diversity.

## Diffusion models vs GANs

GANs train a generator against a discriminator and can be unstable, suffering from mode collapse. Diffusion models have a stable training objective and cover the data distribution better, but sampling is slower because it is iterative.
