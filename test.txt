@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1

echo ========================================
echo   FastAPI 接口测试（修复版）
echo ========================================
echo.

:: 1. 检查服务器是否启动
echo 1. 检查服务器状态...
curl -s -X GET http://localhost:8000/ >nul
if !errorlevel! neq 0 (
    echo    错误：FastAPI服务器未启动！请先运行 python main.py
    pause
    exit /b 1
)
echo    服务器已启动，健康检查正常
echo.

:: 2. 生成JSON请求文件
echo 2. 生成测试数据...
set REQUEST_JSON=test_request.json

:: 使用相对路径，避免路径问题
(
echo {
echo   "ppt_path": "input/presentation.pptx",
echo   "url": "https://www.xiaohongshu.com/user/profile/6549e5640000000004008716",
echo   "style_type": "测评类",
echo   "brand_name": "九牧",
echo   "additional_info": "",
echo   "video_outline_path": "input/video_outline.txt",
echo   "download_images": true
echo }
) > !REQUEST_JSON!

:: 检查JSON文件是否生成成功
if not exist !REQUEST_JSON! (
    echo    错误：生成JSON文件失败！
    pause
    exit /b 1
)
echo    JSON测试数据生成成功
echo.

:: 3. 检查文件是否存在
echo 3. 检查所需文件是否存在...
if not exist "input/presentation.pptx" (
    echo    警告：PPT文件不存在，请确保路径正确
)
if not exist "input/video_outline.txt" (
    echo    警告：视频大纲文件不存在，请确保路径正确
)
echo.

:: 4. 发送请求（绕过代理）
echo 4. 发送请求到内容策略接口...
echo    注意：正在绕过代理直接连接本地服务器...

:: 使用 --noproxy 参数绕过代理
curl --noproxy localhost,127.0.0.1 -v -X POST "http://localhost:8000/generate-content-strategy" ^
     -H "Content-Type: application/json" ^
     -d "@!REQUEST_JSON!"

:: 检查请求是否成功
if !errorlevel! neq 0 (
    echo.
    echo    错误：请求发送失败（可能是网络或接口问题）
) else (
    echo.
    echo    请求发送完成
)
echo.

:: 5. 清理临时文件
echo 5. 清理临时文件...
if exist !REQUEST_JSON! del !REQUEST_JSON! >nul 2>&1
echo    清理完成
echo.

echo 测试结束！
echo 按任意键退出...
pause
endlocal