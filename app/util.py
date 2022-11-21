import os
import asyncio
import logging
import uuid
import itertools
import openai
import replicate
import requests
from PIL import Image

# openai token setup
openai.organization = os.getenv("OPENAI_ORG")
openai.api_key = os.getenv("OPENAI_API_KEY")

# replicate model setup
stable_diffusion_model = replicate.models.get("stability-ai/stable-diffusion")
clip_caption_model = replicate.models.get("rmokady/clip_prefix_caption")


# TODO: add more async processing
async def generate_images(images: list[Image]) -> list[Image]:
    """
    Abstraction of image generation pipeline.

    :param images: list of images to use.
    :return: extension of image set.
    """
    # captioning list of images
    clip_outputs = await asyncio.gather(*map(lambda i: clip_caption_model.predict(i)["title"], images))
    captions = "".join(pred.strip() + "\n" for pred in clip_outputs)
    logging.debug(f"Image captions: {captions}")

    # pass captions through gpt3
    gpt3_response = openai.Completion.create(
        model="text-davinci-002",
        prompt=captions,
        temperature=0.9,
        max_tokens=64
    )
    diffusion_prompts = list(itertools.chain(*[p["text"].splitlines() for p in gpt3_response["choices"]]))
    logging.debug(f"Diffusion prompts: {diffusion_prompts}")

    # generate new images using stable diffusion
    async def create_image(prompt: str) -> list[Image]:
        outputs = await stable_diffusion_model.predict(prompt=prompt, width=512, height=512)
        image_list = await asyncio.gather(lambda url: Image.open(requests.get(url, stream=True).raw), outputs)
        return image_list

    new_images = await asyncio.gather(create_image, diffusion_prompts)
    return new_images


# script to use for testing
# TODO: adapt with async code
if __name__ == "__main__":
    test_dir = "../photos"
    save_dir = "../results"
    original_images = []
    for path in os.listdir(test_dir):
        image = Image.open(f"{test_dir}/{path}")
        if image.mode != "RGB":
            image = image.convert(mode="RGB")
        original_images.append(image)
    output_images = asyncio.run(generate_images(original_images))
    for image in output_images:
        image.save(f"{save_dir}/{uuid.uuid4().hex}.png")
