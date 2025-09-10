import httpx
import time
from config import FEISHU_APP_ID, FEISHU_APP_SECRET

class FeishuClient:
    def __init__(self):
        self.app_id = FEISHU_APP_ID
        self.app_secret = FEISHU_APP_SECRET
        self.client = httpx.AsyncClient(
            base_url="https://open.feishu.cn",
            timeout=httpx.Timeout(30.0)
        )
        self.tenant_access_token = None
        self.token_expire_time = 0

    async def get_tenant_access_token(self) -> str:
        """获取飞书租户访问令牌（自动续期）"""
        if self.tenant_access_token and time.time() < self.token_expire_time:
            return self.tenant_access_token

        url = "/open-apis/auth/v3/tenant_access_token/internal"
        headers = {"Content-Type": "application/json; charset=utf-8"}
        payload = {
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }

        response = await self.client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()

        self.tenant_access_token = result["tenant_access_token"]
        self.token_expire_time = time.time() + result["expire"] - 60  # 提前60秒续期
        return self.tenant_access_token
