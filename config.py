import os
from pathlib import Path

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent

# 火山大模型配置
VOLCANO_API_KEY = os.getenv("VOLCANO_API_KEY", "15e0122b-bf1e-415f-873b-1cb6b39bb612")
VOLCANO_API_URL = os.getenv("VOLCANO_API_URL", "https://ark.cn-beijing.volces.com/api/v3/chat/completions")
VOLCANO_MODEL_NAME = os.getenv("VOLCANO_MODEL_NAME", "doubao-seed-1-6-250615")

# 文件路径配置
DEFAULT_PPT_PATH = os.getenv("PPT_PATH", str(BASE_DIR / "input" / "九牧轻智能马桶brief.pptx"))
DEFAULT_VIDEO_OUTLINE_PATH = os.getenv("VIDEO_OUTLINE_PATH", str(BASE_DIR / "input" / "视频大纲.txt"))
DEFAULT_OUTPUT_DIR = os.getenv("OUTPUT_DIR", str(BASE_DIR / "output"))
DEFAULT_IMAGE_DIR = os.getenv("IMAGE_DIR", str(BASE_DIR / "downloaded_images"))

# 默认参数配置
DEFAULT_URL = os.getenv("DEFAULT_URL", "https://www.xiaohongshu.com/user/profile/6549e5640000000004008716")
DEFAULT_CREATOR_STYLE_DESC = os.getenv("CREATOR_STYLE_DESC", "评测类")
DEFAULT_BRAND_NAME = os.getenv("BRAND_NAME", "九牧黑魔方轻智能马桶（九牧黑魔方）")
DEFAULT_ADDITIONAL_INFO = os.getenv("ADDITIONAL_INFO", "")
DEFAULT_DOWNLOAD_IMAGES = os.getenv("DOWNLOAD_IMAGES", "False").lower() == "true"

# API配置
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))

#飞书配置
# config.py
FEISHU_APP_ID = "cli_a83072e120ff900e"
FEISHU_APP_SECRET = "lFsvXzRYSH61pEZGe9xV0gOtJONfEpD3"
# 在原有config.py中添加你的模板配置
GRAPHIC_OUTLINE_TEMPLATE_SPREADSHEET_TOKEN = "Hk5gsVA0WhIUPstUnB4cXRy1nCc"  # 你的模板token
GRAPHIC_OUTLINE_TEMPLATE_URL = "https://dkke3lyh7o.feishu.cn/sheets/Hk5gsVA0WhIUPstUnB4cXRy1nCc"  # 模板完整URL
FEISHU_FOLDER_TOKEN = "LApffIFkclXULcdj8WLcDiyMnPb"  # 您提供的文件夹token

# 确保目录存在
for directory in [DEFAULT_OUTPUT_DIR, DEFAULT_IMAGE_DIR, BASE_DIR / "input"]:
    os.makedirs(directory, exist_ok=True)