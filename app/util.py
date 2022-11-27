import os
import random
import asyncio
import logging
import uuid
import itertools
from io import BytesIO
import openai
import replicate
import aiohttp
from PIL import Image

from .cfg import MAX_OUTPUT_IMAGES

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
        prediction = replicate.predictions.create(
            version=clip_caption_model.versions.list()[0],
            input={
                "image": file,
                "model": "conceptual-captions",
                "use_beam_search": True,
            },
        )
        while prediction.status not in ["succeeded", "failed", "canceled"]:
            await asyncio.sleep(0.5)
            prediction.reload()
        return prediction.output

    clip_outputs = await asyncio.gather(*map(caption_image, images))
    logging.debug(f"CLIP outputs: {clip_outputs}")
    captions = "".join(pred.strip() + "\n" for pred in clip_outputs)

    # pass captions through gpt3
    gpt3_response = openai.Completion.create(
        model="text-davinci-002", prompt=captions, temperature=0.8, max_tokens=128
    )
    logging.debug(f"GPT3 response: {gpt3_response}")
    # limit to 2 prompts for cost reasons
    diffusion_prompts = list(
        filter(
            None,
            itertools.chain(
                *[p["text"].splitlines() for p in gpt3_response["choices"]]
            ),
        )
    )[:MAX_OUTPUT_IMAGES]
    logging.debug(f"Diffusion prompts: {diffusion_prompts}")

    async def download_image(session: aiohttp.ClientSession, url: str) -> Image:
        async with session.get(url) as response:
            raw = await response.read()
        return Image.open(BytesIO(raw))

    # generate new images using stable diffusion
    async def create_image(prompt: str) -> list[Image]:
        init_image = random.choice(images)
        file = BytesIO()
        init_image.save(file, "PNG")
        try:
            prediction = replicate.predictions.create(
                version=stable_diffusion_model.versions.list()[0],
                input={
                    "prompt": prompt,
                    "width": 512,
                    "height": 512,
                    "init_image": file,
                    "prompt_strength": 0.7,
                },
            )
            while prediction.status not in ["succeeded", "failed", "canceled"]:
                await asyncio.sleep(0.5)
                prediction.reload()
            async with aiohttp.ClientSession() as session:
                image_list = await asyncio.gather(
                    *[download_image(session, url) for url in prediction.output]
                )
            logging.debug(f"Created {len(image_list)} new images")
            return image_list
        except Exception as e:
            logging.warning(e)
            return []

    new_images = await asyncio.gather(*map(create_image, diffusion_prompts))
    return list(itertools.chain(*new_images))


# script to use for testing
if __name__ == "__main__":
    test_dir = "app/photos"
    save_dir = "app/results"
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    original_images = []
    for path in os.listdir(test_dir):
        image = Image.open(f"{test_dir}/{path}")
        if image.mode != "RGB":
            image = image.convert(mode="RGB")
        original_images.append(image)
    output_images = asyncio.run(generate_images(original_images))
    for image in output_images:
        image.save(f"{save_dir}/{uuid.uuid4().hex}.png")
