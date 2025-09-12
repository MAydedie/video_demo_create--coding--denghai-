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

import logging

# 添加日志记录器
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


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
        # 添加令牌缓存相关属性
        self.tenant_access_token = None
        self.token_expire_time = 0  # 令牌过期时间（时间戳）
        logger.info("FeishuSheetManager 初始化完成")

    def _extract_token_from_url(self, url: str) -> str:
        """从飞书表格URL中提取表格token"""
        if not url:
            logger.error("飞书表格URL为空，无法提取token")
            return ""

        # 飞书表格URL格式通常为：https://xxx.feishu.cn/sheets/{token}?xxx
        match = re.search(r'/sheets/([a-zA-Z0-9]+)', url)
        if match:
            token = match.group(1)
            logger.info(f"从URL中提取到表格token: {token}")
            return token
        else:
            logger.error(f"无法从URL中提取表格token: {url}")
            return ""

    async def get_tenant_access_token(self) -> str:
        """获取飞书API的tenant access token（带缓存机制）"""
        # 检查令牌是否有效（提前60秒过期，避免网络延迟导致的问题）
        current_time = time.time()
        if self.tenant_access_token and self.token_expire_time > current_time + 60:
            logger.info("使用缓存的tenant access token")
            return self.tenant_access_token

        try:
            logger.info("开始获取新的tenant access token")
            url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
            headers = {"Content-Type": "application/json; charset=utf-8"}
            payload = {
                "app_id": self.app_id,
                "app_secret": self.app_secret
            }

            response = await self.client.post(url, headers=headers, json=payload)
            response.raise_for_status()  # 抛出HTTP错误状态码
            result = response.json()

            if result.get("code") != 0:
                error_msg = f"获取tenant access token失败: {result.get('msg')} (错误码: {result.get('code')})"
                logger.error(error_msg)
                raise Exception(error_msg)

            # 保存令牌和过期时间
            self.tenant_access_token = result.get("tenant_access_token")
            expire_in = result.get("expire_in", 3600)  # 默认1小时过期
            self.token_expire_time = current_time + expire_in
            logger.info(f"成功获取tenant access token，将在{expire_in}秒后过期")

            return self.tenant_access_token

        except httpx.HTTPError as e:
            error_msg = f"HTTP请求失败: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
        except Exception as e:
            error_msg = f"获取tenant access token出错: {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)

    # 其他已有方法（create_sheet_from_template、fill_cells_in_sheet等）保持不变

    async def create_sheet_from_template(self, title: str) -> Dict[str, Any]:
        """基于模板创建新表格"""
        try:
            logger.info(f"开始创建表格: {title}")
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

            logger.info(f"创建表格请求: {url}")
            logger.info(f"创建表格参数: {payload}")

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, headers=headers, json=payload)
                logger.info(f"创建表格响应状态: {response.status_code}")

                # 处理HTTP错误状态码
                if response.status_code >= 400:
                    error_msg = f"API请求失败 (状态码: {response.status_code}): {response.text}"
                    logger.error(error_msg)
                    return {"status": "error", "message": error_msg}

                # 解析响应JSON
                result = response.json()
                logger.info(f"创建表格响应: {result}")

                if result.get("code") != 0:
                    error_msg = f"飞书接口错误: {result.get('msg')} (错误码: {result.get('code')})"
                    logger.error(error_msg)
                    return {"status": "error", "message": error_msg}

                # 提取表格信息
                if "data" not in result or "file" not in result["data"]:
                    error_msg = f"API返回格式异常: {result}"
                    logger.error(error_msg)
                    return {"status": "error", "message": error_msg}

                spreadsheet_data = result["data"]["file"]
                spreadsheet_token = spreadsheet_data.get("token")
                spreadsheet_url = spreadsheet_data.get("url")

                if not spreadsheet_token or not spreadsheet_url:
                    error_msg = f"缺少表格关键信息: {spreadsheet_data}"
                    logger.error(error_msg)
                    return {"status": "error", "message": error_msg}

                # 获取sheet_id
                meta_url = f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/metainfo"
                meta_response = await client.get(meta_url, headers=headers)
                meta_response.raise_for_status()
                meta_result = meta_response.json()

                if meta_result.get("code") != 0:
                    error_msg = f"获取sheet_id失败: {meta_result.get('msg')}"
                    logger.error(error_msg)
                    return {"status": "error", "message": error_msg}

                if not meta_result.get("data", {}).get("sheets"):
                    error_msg = "表格中未找到工作表"
                    logger.error(error_msg)
                    return {"status": "error", "message": error_msg}

                first_sheet = meta_result["data"]["sheets"][0]
                sheet_id = first_sheet.get("sheetId") or first_sheet.get("sheet_id") or "0"

                logger.info(f"成功创建表格: {spreadsheet_url}, sheet_id: {sheet_id}")
                return {
                    "status": "success",
                    "spreadsheet_token": spreadsheet_token,
                    "url": spreadsheet_url,
                    "sheet_id": sheet_id
                }

        except Exception as e:
            error_msg = f"创建表格出错: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"status": "error", "message": error_msg}

    async def fill_cells_in_sheet(self, spreadsheet_token: str, sheet_id: str, cell_data: Dict[str, str]) -> Dict[
        str, Any]:
        """向表格写入数据"""
        if not all(isinstance(x, str) for x in [spreadsheet_token, sheet_id]):
            error_msg = "spreadsheet_token或sheet_id不是字符串类型"
            logger.error(error_msg)
            return {"status": "error", "message": error_msg}

        if not isinstance(cell_data, dict):
            error_msg = "cell_data必须是字典类型"
            logger.error(error_msg)
            return {"status": "error", "message": error_msg}

        try:
            logger.info(f"开始向表格 {spreadsheet_token} 写入数据")
            logger.info(f"要写入的单元格数据: {cell_data}")

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
                    logger.warning(f"跳过无效的单元格数据: {cell} -> {value}")
                    continue

                # 构造范围，使用A1表示法，格式为 "sheet_id!cell:cell"
                range_str = f"{sheet_id}!{cell}:{cell}"
                value_ranges.append({
                    "range": range_str,
                    "values": [[value]]
                })

            payload = {
                "valueRanges": value_ranges
            }

            logger.info(f"写入请求: {url}")
            logger.info(f"写入数据: {payload}")

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                result = response.json()

                logger.info(f"写入响应: {result}")

                if result.get("code") == 0:
                    logger.info("写入成功")
                    return {"status": "success", "message": "写入成功"}
                else:
                    error_msg = f"写入失败: {result.get('msg')}"
                    logger.error(error_msg)
                    return {"status": "error", "message": error_msg}

        except httpx.HTTPError as e:
            error_msg = f"写入失败: {str(e)}"
            if e.response is not None:
                error_msg += f"\n错误响应: {e.response.text}"
            logger.error(error_msg)
            return {"status": "error", "message": error_msg}
        except Exception as e:
            error_msg = f"写入失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"status": "error", "message": error_msg}

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
        logger.info("FeishuSpreadsheetUtil 初始化完成")

    async def full_flow(self, video_script: str, strategy_result: str, shot_list: list = None) -> Dict[str, Any]:
        """完整流程：创建表格并写入数据"""
        try:
            logger.info("开始处理飞书表格流程")

            # 初始化默认值
            title = f"内容策略_{time.strftime('%Y%m%d%H%M')}"
            text = ""
            label = "自动生成"

            # 确保shot_list不为None
            if shot_list is None:
                shot_list = []

            # 1. 解析视频脚本（关键修复）
            logger.info(f"开始解析视频脚本: {type(video_script)}")
            logger.info(f"视频脚本内容: {video_script[:200]}...")  # 只记录前200字符避免日志过长

            try:
                # 首先尝试解析为完整的API响应
                response_data = json.loads(video_script)
                logger.info("成功解析为API响应格式")

                # 提取content字段
                if ("choices" in response_data and
                        len(response_data["choices"]) > 0 and
                        "message" in response_data["choices"][0] and
                        "content" in response_data["choices"][0]["message"]):

                    content_str = response_data["choices"][0]["message"]["content"]
                    logger.info(f"提取到content字段: {content_str[:100]}...")

                    # 尝试解析content字段中的JSON
                    try:
                        content_data = json.loads(content_str)
                        if isinstance(content_data, dict):
                            title = content_data.get("title", title)
                            text = content_data.get("text", "")
                            label = content_data.get("label", label)
                            logger.info(f"从content中提取: title={title}, text长度={len(text)}, label={label}")
                        else:
                            logger.warning("content字段不是字典格式")
                    except json.JSONDecodeError:
                        logger.warning("content字段不是有效JSON，使用原始内容")
                        text = content_str
                else:
                    logger.warning("API响应格式不符合预期，尝试直接提取字段")
                    # 尝试直接从响应中提取字段
                    title = response_data.get("title", title)
                    text = response_data.get("text", "")
                    label = response_data.get("label", label)

            except json.JSONDecodeError:
                logger.warning("视频脚本不是有效JSON，尝试其他解析方式")
                # 尝试提取代码块中的JSON
                json_match = re.search(r'```(?:json)?\s*(\{.*\})\s*```', video_script, re.DOTALL)
                if json_match:
                    try:
                        script_data = json.loads(json_match.group(1))
                        if isinstance(script_data, dict):
                            title = script_data.get("title", title)
                            text = script_data.get("text", "")
                            label = script_data.get("label", label)
                        logger.info(f"从代码块中提取: title={title}, text长度={len(text)}, label={label}")
                    except json.JSONDecodeError:
                        logger.warning("代码块中的JSON解析失败")
                        text = video_script
                else:
                    logger.warning("没有找到JSON代码块，使用原始文本作为正文")
                    text = video_script

            # 确保标题不为空
            title = title or f"内容策略_{time.strftime('%Y%m%d%H%M')}"
            # 清理标题中的特殊字符
            title = re.sub(r'[\\/*?:"<>|]', '-', title)
            logger.info(f"最终使用的标题: {title}")

            # 2. 准备要写入的数据
            cell_data = {
                "B9": text[:1000] if len(text) > 1000 else text,  # 正文写入B9
                "B10": label[:100] if len(label) > 100 else label  # 标签写入B10
            }
            logger.info(f"基础单元格数据: B9长度={len(cell_data['B9'])}, B10={cell_data['B10']}")

            # 3. 添加分镜脚本数据（从A29开始）- 保持不变
            if shot_list:
                logger.info(f"开始处理分镜数据，共 {len(shot_list)} 个镜头")
                for i, shot in enumerate(shot_list):
                    row = 29 + i  # 从第29行开始

                    if isinstance(shot, dict):
                        cell_data[f"A{row}"] = shot.get("景别", "")
                        cell_data[f"B{row}"] = shot.get("画面", "")
                        cell_data[f"C{row}"] = shot.get("口播", "")
                        cell_data[f"D{row}"] = shot.get("花字", "")
                        cell_data[f"E{row}"] = shot.get("时长", "")
                        cell_data[f"F{row}"] = shot.get("备注", "")
                    elif isinstance(shot, str):
                        cell_data[f"A{row}"] = shot

                logger.info(f"分镜处理完成，共添加 {len(shot_list)} 个镜头的单元格")
            else:
                logger.warning("没有分镜数据，跳过分镜写入逻辑")

            # 4. 创建表格并写入数据
            logger.info(
                f"准备提交的最终单元格数据: B9长度={len(cell_data.get('B9', ''))}, B10={cell_data.get('B10', '')}")
            result = await self.sheet_manager.create_and_write(title, cell_data)

            return result

        except Exception as e:
            error_msg = f"处理飞书表格时出错: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"status": "error", "message": error_msg}