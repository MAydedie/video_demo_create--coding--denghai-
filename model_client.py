import httpx
import time
from config import FEISHU_APP_ID, FEISHU_APP_SECRET


class FeishuClient:
    def __init__(self):
        self.app_id = FEISHU_APP_ID
        self.app_secret = FEISHU_APP_SECRET
        self.tenant_access_token = None
        self.token_expire_time = 0
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(30.0))

    async def get_tenant_access_token(self) -> str:
        if self.tenant_access_token and time.time() < self.token_expire_time:
            return self.tenant_access_token

        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        headers = {"Content-Type": "application/json; charset=utf-8"}
        payload = {
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }

        try:
            response = await self.client.post(url, headers=headers, json=payload)
            response.raise_for_status()

            # 确保响应是JSON格式
            try:
                result = response.json()
            except ValueError:
                raise Exception(f"飞书令牌接口返回非JSON数据: {response.text}")

            if "tenant_access_token" not in result:
                raise Exception(f"飞书令牌接口缺少关键字段: {result}")

            self.tenant_access_token = result["tenant_access_token"]
            self.token_expire_time = time.time() + result.get("expire", 3600) - 60
            return self.tenant_access_token

        except httpx.HTTPError as e:
            error_msg = f"获取飞书令牌失败: {str(e)}"
            if e.response is not None:
                error_msg += f"\n响应状态码: {e.response.status_code}"
                error_msg += f"\n响应内容: {e.response.text}"
            raise Exception(error_msg)
        except Exception as e:
            raise Exception(f"处理令牌时出错: {str(e)}")