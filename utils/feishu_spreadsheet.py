# 修改后的feishu_spreadsheet.py
import asyncio
import time
import re
import json
from typing import Dict, Any
import httpx
from config import (
    FEISHU_APP_ID,
    FEISHU_APP_SECRET,
    GRAPHIC_OUTLINE_TEMPLATE_URL,
    FEISHU_FOLDER_TOKEN
)


class FeishuSheetManager:
    """飞书表格管理器，处理表格创建、写入、链接返回"""

    def __init__(self):
        self.app_id = FEISHU_APP_ID
        self.app_secret = FEISHU_APP_SECRET
        self.template_url = GRAPHIC_OUTLINE_TEMPLATE_URL
        self.template_token = self._extract_token_from_url(GRAPHIC_OUTLINE_TEMPLATE_URL)
        self.folder_token = FEISHU_FOLDER_TOKEN
        self.timeout = 30.0
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(30.0))

    def _extract_token_from_url(self, url: str) -> str:
        """从飞书表格URL中提取token"""
        match = re.search(r'/sheets/([A-Za-z0-9_\-]+)', url)
        if not match:
            raise ValueError(f"无效的飞书表格URL：{url}")
        return match.group(1)

    async def get_tenant_access_token(self) -> str:
        """获取租户访问令牌（自动续期）"""
        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        headers = {"Content-Type": "application/json; charset=utf-8"}
        payload = {
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }

        try:
            response = await self.client.post(url, headers=headers, json=payload)
            response.raise_for_status()

            result = response.json()
            if "tenant_access_token" not in result:
                raise Exception(f"飞书令牌接口缺少关键字段: {result}")

            return result["tenant_access_token"]

        except httpx.HTTPError as e:
            error_msg = f"获取飞书令牌失败: {str(e)}"
            if e.response is not None:
                error_msg += f"\n响应状态码: {e.response.status_code}"
                error_msg += f"\n响应内容: {e.response.text}"
            raise Exception(error_msg)
        except Exception as e:
            raise Exception(f"处理令牌时出错: {str(e)}")

    async def create_sheet_from_template(self, title: str) -> Dict[str, Any]:
        """基于模板创建新表格"""
        try:
            token = await self.get_tenant_access_token()
            url = f"https://open.feishu.cn/open-apis/drive/v1/files/{self.template_token}/copy"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=utf-8"
            }
            payload = {
                "name": f"{title} - 内容策略",
                "type": "sheet",
                "folder_token": self.folder_token
            }

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, headers=headers, json=payload)

                # 处理HTTP错误状态码
                if response.status_code >= 400:
                    return {"status": "error",
                            "message": f"API请求失败 (状态码: {response.status_code}): {response.text}"}

                # 解析响应JSON
                result = response.json()

                if result.get("code") != 0:
                    return {"status": "error",
                            "message": f"飞书接口错误: {result.get('msg')} (错误码: {result.get('code')})"}

                # 提取表格信息
                if "data" not in result or "file" not in result["data"]:
                    return {"status": "error", "message": f"API返回格式异常: {result}"}

                spreadsheet_data = result["data"]["file"]
                spreadsheet_token = spreadsheet_data.get("token")
                spreadsheet_url = spreadsheet_data.get("url")

                if not spreadsheet_token or not spreadsheet_url:
                    return {"status": "error", "message": f"缺少表格关键信息: {spreadsheet_data}"}

                # 获取sheet_id
                meta_url = f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/metainfo"
                meta_response = await client.get(meta_url, headers=headers)
                meta_response.raise_for_status()
                meta_result = meta_response.json()

                if meta_result.get("code") != 0:
                    return {"status": "error", "message": f"获取sheet_id失败: {meta_result.get('msg')}"}

                if not meta_result.get("data", {}).get("sheets"):
                    return {"status": "error", "message": "表格中未找到工作表"}

                first_sheet = meta_result["data"]["sheets"][0]
                sheet_id = first_sheet.get("sheetId") or first_sheet.get("sheet_id") or "0"

                return {
                    "status": "success",
                    "spreadsheet_token": spreadsheet_token,
                    "url": spreadsheet_url,
                    "sheet_id": sheet_id
                }

        except Exception as e:
            return {"status": "error", "message": f"创建表格出错: {str(e)}"}

    async def fill_cells_in_sheet(self, spreadsheet_token: str, sheet_id: str, cell_data: Dict[str, str]) -> Dict[
        str, Any]:
        """向表格写入数据"""
        if not all(isinstance(x, str) for x in [spreadsheet_token, sheet_id]):
            return {"status": "error", "message": "spreadsheet_token或sheet_id不是字符串类型"}

        if not isinstance(cell_data, dict):
            return {"status": "error", "message": "cell_data必须是字典类型"}

        try:
            token = await self.get_tenant_access_token()

            # 使用v2版本的API
            url = f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/values_batch_update"
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json; charset=utf-8"
            }

            value_ranges = []
            for cell, value in cell_data.items():
                if not isinstance(cell, str) or not isinstance(value, str):
                    continue

                # 构造范围，使用A1表示法，格式为 "sheet_id!cell:cell"
                range_str = f"{sheet_id}!{cell}:{cell}"
                value_ranges.append({
                    "range": range_str,
                    "values": [[value]]  # 确保值是纯文本，不包含JSON格式
                })

            payload = {
                "valueRanges": value_ranges
            }

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                result = response.json()

                if result.get("code") == 0:
                    return {"status": "success", "message": "写入成功"}
                else:
                    return {"status": "error", "message": f"写入失败: {result.get('msg')}"}

        except httpx.HTTPError as e:
            error_msg = f"写入失败: {str(e)}"
            if e.response is not None:
                error_msg += f"\n错误响应: {e.response.text}"
            return {"status": "error", "message": error_msg}
        except Exception as e:
            return {"status": "error", "message": f"写入失败: {str(e)}"}

    async def create_and_write(self, title: str, cell_data: Dict[str, str]) -> Dict[str, Any]:
        """完整流程：创建表格并写入数据"""
        create_result = await self.create_sheet_from_template(title)
        if create_result["status"] != "success":
            return create_result

        # 添加一点延迟，确保表格完全创建
        await asyncio.sleep(1)

        write_result = await self.fill_cells_in_sheet(
            spreadsheet_token=create_result["spreadsheet_token"],
            sheet_id=create_result["sheet_id"],
            cell_data=cell_data
        )

        if write_result["status"] != "success":
            return {
                "status": "error",
                "message": f"表格创建成功，但写入数据失败: {write_result.get('message')}",
                "url": create_result["url"]
            }

        return {
            "status": "success",
            "message": "表格创建并写入成功",
            "spreadsheet_url": create_result["url"],
            "spreadsheet_token": create_result["spreadsheet_token"]
        }


class FeishuSpreadsheetUtil:
    def __init__(self):
        self.sheet_manager = FeishuSheetManager()

    async def full_flow(self, video_script: str, strategy_result: str) -> Dict[str, Any]:
        """完整流程：创建表格并写入数据"""
        try:
            # 尝试解析视频脚本JSON
            title = f"内容策略_{time.strftime('%Y%m%d%H%M')}"
            text = ""
            label = "自动生成"

            try:
                # 首先尝试直接解析
                script_data = json.loads(video_script)

                # 检查是否是双层嵌套结构（包含content字段）
                if "content" in script_data and isinstance(script_data["content"], str):
                    # 如果是双层嵌套结构，解析content字段
                    content_data = json.loads(script_data["content"])
                    title = content_data.get("title", title)
                    text = content_data.get("text", "")
                    label = content_data.get("label", label)
                else:
                    # 如果不是双层嵌套结构，直接使用字段
                    title = script_data.get("title", title)
                    text = script_data.get("text", "")
                    label = script_data.get("label", label)

            except json.JSONDecodeError:
                # 如果直接解析失败，尝试提取可能被代码块包裹的JSON
                json_match = re.search(r'```(?:json)?\s*(\{.*\})\s*```', video_script, re.DOTALL)
                if json_match:
                    script_data = json.loads(json_match.group(1))

                    # 检查是否是双层嵌套结构
                    if "content" in script_data and isinstance(script_data["content"], str):
                        content_data = json.loads(script_data["content"])
                        title = content_data.get("title", title)
                        text = content_data.get("text", "")
                        label = content_data.get("label", label)
                    else:
                        title = script_data.get("title", title)
                        text = script_data.get("text", "")
                        label = script_data.get("label", label)
                else:
                    # 如果还是失败，使用原始内容作为text
                    text = video_script
                    # 从原始文本中尝试提取标题（如果可能）
                    if not title or title.startswith("内容策略_"):
                        lines = [line.strip() for line in video_script.split('\n') if line.strip()]
                        if lines:
                            title = lines[0][:50]  # 取第一行作为标题，限制长度

            # 确保标题不为空且格式正确
            title = title or f"内容策略_{time.strftime('%Y%m%d%H%M')}"
            # 清理标题中的特殊字符
            title = re.sub(r'[\\/*?:"<>|]', '-', title)

            # 准备要写入的数据，确保是纯文本格式
            cell_data = {
                "B9": text[:1000] if len(text) > 1000 else text,  # 将text写入B9单元格，限制长度
                "B10": label[:100] if len(label) > 100 else label  # 将label写入B10单元格，限制长度
            }

            # 创建表格并写入数据
            result = await self.sheet_manager.create_and_write(title, cell_data)

            return result

        except Exception as e:
            return {"status": "error", "message": f"处理飞书表格时出错: {str(e)}"}
