import requests
import base64
import time
from pathlib import Path
from PIL import Image
import io

def compress_image(image_path, quality=80):
    """将图片压缩至1K分辨率（最大1920×1080）并返回base64编码"""
    # 1K标准分辨率（宽×高，主流为1920×1080，即全高清FHD）
    target_max_size = (1920, 1080)
    
    with Image.open(image_path) as img:
        # 转换图片模式（兼容JPEG格式）
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        
        # 按比例缩放至1K以内（保持宽高比，避免拉伸）
        img.thumbnail(target_max_size)
        
        # 保存到字节流
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=quality)
        
        # 编码为base64字符串
        return base64.b64encode(buffer.getvalue()).decode()

def run_inference(image_path: str, question: str) -> str:
    try:
        # 关键：压缩图片后再编码
        b64_image = compress_image(image_path)
    except Exception as e:
        return f"图片处理出错: {e}"

    # 构建请求数据（使用OpenAI兼容格式）
    url = "http://localhost:5001/v1/chat/completions"
    data = {
        "model": "/home/hr/Zzyq/model/Awaker",
        # "model": "Awaker",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": question},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"}}
                ]
            }
        ],
        "temperature": 0.1,
        "max_tokens": 1024
    }

    try:
        # 发送请求并获取结果
        resp = requests.post(url, json=data, timeout=60)
        resp.raise_for_status()  # 触发HTTP错误（如400/500）
        return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        # 捕获并返回错误信息
        return f"推理出错: {e}\n{resp.text[:500] if 'resp' in locals() else ''}"

if __name__ == "__main__":
    t1 = time.time()
    # 测试：分析图片是否为道路路面
    result = run_inference(
        "/home/hr/Zzyq/img/DJI_20251017152549_0001_WIDE.jpg",
        "请分析这张图片路面，是否存在严重的坑洼或坑槽。状态:存在或者不存在;描述:请描述你的理由和思考过程，必须按照如下格式返回:[{'状态':"",'描述':""}]"
    )
    print(result)
    print(f"耗时: {time.time() - t1:.2f}秒")