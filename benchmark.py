# 模型性能基准测试
import logging
import time
from fastapi import WebSocket

import torch
from PIL import Image
from transformers import (
    BertForSequenceClassification,
    BertTokenizer,
    CLIPModel,
    CLIPProcessor,
)

from config import model_config


class Benchmark:
    def __init__(self, ws: WebSocket | None = None):
        self.logger = logging.getLogger(__name__)
        self.ws = ws
        self.test_times = 100  # 测试次数

    async def send_text(self, text: str):
        if self.ws:
            await self.ws.send_text(text)
        self.logger.info(text)

    async def run(self):
        device_list = ["cpu", "cuda", "mps"]  # 推理设备，可选cpu、cuda、mps
        image = Image.open("test.png")  # 测试图片。图片大小影响速度，一般相机照片为4000x3000。图片内容不影响速度。
        input_text = "This is a test sentence."  # 测试文本

        await self.send_text(f"你使用的语言为{model_config.value.language}。")
        # FIXME: websocket 会在这里卡住
        await self.send_text("Loading models...")
        is_chinese = model_config.value.language == "Chinese"
        clip_model = CLIPModel.from_pretrained(model_config.value.name)
        clip_processor = CLIPProcessor.from_pretrained(model_config.value.name)
        if is_chinese:
            text_tokenizer = BertTokenizer.from_pretrained(
                model_config.value.textModelName
            )
            text_encoder = BertForSequenceClassification.from_pretrained(
                model_config.value.textModelName
            ).eval()
        await self.send_text("Models loaded.")

        # 图像处理性能基准测试
        await self.send_text("开始进行图像处理性能基准测试。用时越短越好。")
        min_time = float("inf")
        recommend_device = ""
        for device in device_list:
            try:
                clip_model = clip_model.to(torch.device(device))
            except (AssertionError, RuntimeError):
                await self.send_text(f"该平台不支持{device}，已跳过。")
                continue
            t0 = time.time()
            for i in range(self.test_times):
                inputs = clip_processor(
                    images=image, return_tensors="pt", padding=True
                )["pixel_values"].to(torch.device(device))
                feature = clip_model.get_image_features(inputs).detach().cpu().numpy()
            cost_time = time.time() - t0
            await self.send_text(f"设备：{device} 用时：{cost_time:.3f} 秒")
            if cost_time < min_time:
                min_time = cost_time
                recommend_device = device
        await self.send_text(f"图像处理建议使用设备：{recommend_device}")

        # 文字处理性能基准测试
        await self.send_text("开始进行文字处理性能基准测试。用时越短越好。")
        min_time = float("inf")
        recommend_device = ""
        for device in device_list:
            try:
                if is_chinese:
                    text_encoder = text_encoder.to(torch.device(device))
                else:
                    clip_model = clip_model.to(torch.device(device))
            except (AssertionError, RuntimeError):
                await self.send_text(f"该平台不支持{device}，已跳过。")
                continue
            t0 = time.time()
            for i in range(self.test_times):
                if is_chinese:
                    text = text_tokenizer(
                        input_text, return_tensors="pt", padding=True
                    )["input_ids"].to(torch.device(device))
                    text_features = text_encoder(text).logits.detach().cpu().numpy()
                else:
                    text = clip_processor(
                        text=input_text, return_tensors="pt", padding=True
                    )["input_ids"].to(torch.device(device))
                    text_features = (
                        clip_model.get_text_features(text).detach().cpu().numpy()
                    )
            cost_time = time.time() - t0
            await self.send_text(f"设备：{device} 用时：{cost_time:.3f} 秒")
            if cost_time < min_time:
                min_time = cost_time
                recommend_device = device
        await self.send_text(f"文字处理建议使用设备：{recommend_device}")

        await self.send_text("测试完毕！")


if __name__ == "__main__":
    import asyncio

    benchmark = Benchmark()
    logging.basicConfig(level=logging.INFO)
    asyncio.run(benchmark.run())
