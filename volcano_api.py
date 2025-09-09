import aiohttp
import asyncio
import base64
import os
import json
import time
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


class VolcanoAPI:
    def __init__(self, api_key, api_url, model_name):
        self.api_key = api_key
        self.api_url = api_url
        self.model_name = model_name
        # 火山官方支持的所有图片格式
        self.SUPPORTED_IMAGE_FORMATS = {
            '.jpg': 'jpeg',
            '.jpeg': 'jpeg',
            '.png': 'png',
            '.gif': 'gif',
            '.webp': 'webp',
            '.bmp': 'bmp',
            '.dib': 'bmp',
            '.tiff': 'tiff',
            '.tif': 'tiff',
            '.ico': 'ico',
            '.icns': 'icns',
            '.sgi': 'sgi',
            '.j2c': 'jp2',
            '.j2k': 'jp2',
            '.jp2': 'jp2',
            '.jpc': 'jp2',
            '.jpf': 'jp2',
            '.jpx': 'jp2',
            '.heic': 'heic',
            '.heif': 'heif'
        }

    def encode_image_to_base64(self, image_path):
        """将图片编码为base64格式"""
        try:
            ext = os.path.splitext(image_path.lower())[1]
            if ext not in self.SUPPORTED_IMAGE_FORMATS:
                logger.warning(f"不支持的图片格式: {ext}，跳过该图片")
                return None, None

            img_format = self.SUPPORTED_IMAGE_FORMATS[ext]
            with open(image_path, "rb") as image_file:
                image_data = base64.b64encode(image_file.read()).decode('utf-8')

            if ext in ['.heic', '.heif']:
                logger.info(f"注意：{ext}格式需要doubao-1.5-vision-pro及以上模型支持")

            return img_format, image_data
        except Exception as e:
            logger.error(f"编码图片时出错: {str(e)}")
            return None, None

    async def call_volcano_api(self, system_prompt, user_prompt, image_paths=None, max_retries=3):
        """异步调用火山API（添加关闭深度思考配置）"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        # 构建消息体
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": [{"type": "text", "text": user_prompt}]}
        ]

        # 添加图片
        image_count = 0
        if image_paths:
            for image_path in image_paths:
                if image_count >= 3:
                    break
                img_format, img_base64 = self.encode_image_to_base64(image_path)
                if img_format and img_base64:
                    messages[1]["content"].append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/{img_format};base64,{img_base64}"}
                    })
                    image_count += 1

        # 核心修改：添加 thinking 字段强制关闭深度思考
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 2048,
            "stream": False,
            "thinking": {"type": "disabled"}  # 强制关闭深度思考（针对支持的模型）
        }

        # 异步请求
        for attempt in range(max_retries):
            try:
                logger.info(f"尝试第 {attempt + 1} 次API调用...")

                async with aiohttp.ClientSession() as session:
                    async with session.post(
                            self.api_url,
                            headers=headers,
                            json=payload,
                            timeout=60  # 普通模型超时可缩短至60秒（原120秒）
                    ) as response:

                        logger.info(f"响应状态码: {response.status}")
                        response_text = await response.text()
                        logger.info(f"响应内容: {response_text[:500]}...")

                        if response.status == 400:
                            return f"400错误（请求格式错误）: {response_text}"
                        if response.status == 401:
                            return "401错误: API密钥无效"
                        if response.status == 404:
                            return "404错误: API URL不正确"

                        response.raise_for_status()
                        result = await response.json()
                        if "choices" in result and len(result["choices"]) > 0:
                            return result["choices"][0]["message"]["content"]
                        else:
                            return f"处理失败: 空结果，响应: {result}"

            except aiohttp.ClientError as e:
                logger.error(f"HTTP错误 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    wait_time = 5 * (attempt + 1)
                    logger.info(f"等待{wait_time}秒后重试...")
                    await asyncio.sleep(wait_time)
                else:
                    return f"处理失败: {str(e)}"
            except Exception as e:
                logger.error(f"未知错误 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(5 * (attempt + 1))
                else:
                    return f"处理失败: {str(e)}"

        return "处理失败: 超过最大重试次数"
