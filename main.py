import os
import uuid
import itertools
import torch
import openai
import replicate
import requests
from transformers import VisionEncoderDecoderModel, ViTFeatureExtractor, AutoTokenizer
from PIL import Image

# openai token setup
openai.organization = os.getenv("OPENAI_ORG")
openai.api_key = os.getenv("OPENAI_API_KEY")

# stable diffusion setup
stable_diffusion_model = replicate.models.get("stability-ai/stable-diffusion")

# captioning model setup
model = VisionEncoderDecoderModel.from_pretrained("nlpconnect/vit-gpt2-image-captioning")
feature_extractor = ViTFeatureExtractor.from_pretrained("nlpconnect/vit-gpt2-image-captioning")
tokenizer = AutoTokenizer.from_pretrained("nlpconnect/vit-gpt2-image-captioning")
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)
gen_kwargs = {"max_length": 16, "num_beams": 4}


def gen_images(images: list[Image]) -> list[Image]:
    pixel_values = feature_extractor(images=images, return_tensors="pt").pixel_values
    pixel_values = pixel_values.to(device)

    output_ids = model.generate(pixel_values, **gen_kwargs)

    captions = tokenizer.batch_decode(output_ids, skip_special_tokens=True)
    captions = "".join(pred.strip() + "\n" for pred in captions)

    gpt3_response = openai.Completion.create(
        model="text-davinci-002",
        prompt=captions,
        temperature=0.9,
        max_tokens=64
    )

    diffusion_prompts = list(itertools.chain(*[p["text"].splitlines() for p in gpt3_response["choices"]]))
    print(diffusion_prompts)
    new_images = []
    for prompt in diffusion_prompts[:4]:
        outputs = stable_diffusion_model.predict(prompt=prompt, width=512, height=512)
        for url in outputs:
            new_images.append(Image.open(requests.get(url, stream=True).raw))
    return new_images


if __name__ == "__main__":
    test_dir = "photos"
    save_dir = "results"
    original_images = []
    for path in os.listdir(test_dir):
        image = Image.open(f"{test_dir}/{path}")
        if image.mode != "RGB":
            image = image.convert(mode="RGB")
        original_images.append(image)
    output_images = gen_images(original_images)
    for image in output_images:
        image.save(f"{save_dir}/{uuid.uuid4().hex}.png")
