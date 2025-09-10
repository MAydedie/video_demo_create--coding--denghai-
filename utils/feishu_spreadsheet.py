import asyncio
import time  # 新增：导入time模块，解决'time'未解析问题
from typing import Dict, Any
from model_client import FeishuClient
# 新增：导入GRAPHIC_OUTLINE_TEMPLATE_URL，解决模板URL未解析问题
from config import GRAPHIC_OUTLINE_TEMPLATE_SPREADSHEET_TOKEN, GRAPHIC_OUTLINE_TEMPLATE_URL


class FeishuSpreadsheetUtil:
    def __init__(self):
        self.feishu_client = FeishuClient()
        self.template_token = GRAPHIC_OUTLINE_TEMPLATE_SPREADSHEET_TOKEN  # 你的模板token
        self.template_url = GRAPHIC_OUTLINE_TEMPLATE_URL  # 缓存模板URL

    async def create_spreadsheet_from_template(self, title: str) -> Dict[str, Any]:
        """基于你的模板创建表格（精准适配）"""
        try:
            token = await self.feishu_client.get_tenant_access_token()
            url = f"/open-apis/drive/v1/files/{self.template_token}/copy"
            headers = {"Authorization": f"Bearer {token}"}
            payload = {
                "name": title,  # 新表格标题
                "folder_token": ""  # 模板存储文件夹（留空则与模板同目录）
            }

            response = await self.feishu_client.client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()

            spreadsheet_data = result["data"]["file"]
            return {
                "spreadsheet_token": spreadsheet_data["token"],
                "url": spreadsheet_data["url"],
                "sheet_id": spreadsheet_data["sheet_ids"][0],
                "status": "success"
            }
        except Exception as e:
            return {"status": "error", "message": f"模板创建失败：{str(e)}"}

    async def write_to_template_cells(self, spreadsheet_token: str, sheet_id: str, video_script: str,
                                      strategy_result: str) -> bool:
        """按你的模板结构写入数据（精准定位单元格）"""
        try:
            token = await self.feishu_client.get_tenant_access_token()
            url = f"/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/values"
            headers = {"Authorization": f"Bearer {token}"}

            payload = {
                "valueRange": {
                    "range": f"{sheet_id}!B2:B3",  # 仅写入B列内容区
                    "values": [
                        [video_script],  # B2: 视频脚本配文
                        [strategy_result]  # B3: 策略结果
                    ]
                }
            }

            response = await self.feishu_client.client.put(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json().get("code") == 0
        except Exception as e:
            return False

    async def full_flow(self, video_script: str, strategy_result: str) -> Dict[str, Any]:
        """完整流程（严格适配你的模板）"""
        # 使用导入的time模块生成标题（修复'time'未解析问题）
        title = f"内容策略_{time.strftime('%Y%m%d%H%M')}"
        create_result = await self.create_spreadsheet_from_template(title)

        if create_result["status"] != "success":
            return create_result

        write_success = await self.write_to_template_cells(
            spreadsheet_token=create_result["spreadsheet_token"],
            sheet_id=create_result["sheet_id"],
            video_script=video_script,
            strategy_result=strategy_result
        )

        return {
            "status": "success" if write_success else "error",
            "spreadsheet_url": create_result["url"],
            "template_used": self.template_url,  # 使用缓存的模板URL（修复未解析问题）
            "message": "已按模板写入数据" if write_success else "写入失败"
        }
