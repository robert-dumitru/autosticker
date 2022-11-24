import os
import random
import asyncio
import logging
import uuid
import itertools
from io import BytesIO
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


async def generate_images(images: list[Image]) -> list[Image]:
    """
    Abstraction of image generation pipeline.

    :param images: list of images to use.
    :return: extension of image set.
    """
    # captioning list of images
    async def caption_image(image: Image) -> str:
        file = BytesIO()
        image.save(file, "PNG")
        return clip_caption_model.predict(image=file, model="conceptual-captions", use_beam_search=True)

    clip_outputs = await asyncio.gather(*map(caption_image, images))
    captions = "".join(pred.strip() + "\n" for pred in clip_outputs)
    logging.debug(f"Image captions: {captions}")

    # pass captions through gpt3
    gpt3_response = openai.Completion.create(
        model="text-davinci-002",
        prompt=captions,
        temperature=0.9,
        max_tokens=128
    )
    diffusion_prompts = list(itertools.chain(*[p["text"].splitlines() for p in gpt3_response["choices"]]))
    logging.debug(f"Diffusion prompts: {diffusion_prompts}")

    async def download_image(url: str) -> Image:
        return Image.open(requests.get(url, stream=True).raw)

    # generate new images using stable diffusion
    async def create_image(prompt: str) -> list[Image]:
        init_image = random.choice(images)
        file = BytesIO()
        init_image.save(file, "PNG")
        outputs = stable_diffusion_model.predict(
            prompt=prompt,
            width=512,
            height=512,
            init_image=file,
            prompt_strength=0.6
        )
        image_list = await asyncio.gather(*map(download_image, outputs))
        return image_list

    new_images = await asyncio.gather(*map(create_image, diffusion_prompts))
    return list(itertools.chain(*new_images))


# script to use for testing
if __name__ == "__main__":
    test_dir = "app/photos"
    save_dir = "app/results"
    original_images = []
    for path in os.listdir(test_dir):
        image = Image.open(f"{test_dir}/{path}")
        if image.mode != "RGB":
            image = image.convert(mode="RGB")
        original_images.append(image)
    output_images = asyncio.run(generate_images(original_images))
    for image in output_images:
        image.save(f"{save_dir}/{uuid.uuid4().hex}.png")
