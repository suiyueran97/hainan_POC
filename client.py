# client.py
# import asyncio
# import json
# import httpx

# async def send_request():
#     url = "http://127.0.0.1:5000/vision_engine/submit_tasks"
#     # url = "http://127.0.0.1:8000/vision_engine/analysis"

#     # 构造任务列表（可按需替换路径）
#     tasks = [
#         # {
#         #     "identifyType": ["道路-积水", "道路-路面塌陷", "道路-树木倒伏"],
#         #     "ftp_path": "/home/sky/Data/YU/huaruan/img/demo.jpeg"
#         # },
#         {
#             "identifyType": ["道路-树木倒伏"],
#             "ftp_path": "/home/sky/Data/YU/huaruan/img/demo.jpeg"
#         }
#         # {
#         #     "identifyType": ["桥梁涵洞-裂缝"],
#         #     "ftp_path": "/home/sky/Data/YU/huaruan/img/demo.jpeg"
#         # },
#         # {
#         #     "identifyType": ["道路-积水"],
#         #     "ftp_path": "/home/sky/Data/YU/huaruan/img/demo.jpeg"
#         # },
#         # {
#         #     "identifyType": ["道路-排水渠堵塞"],
#         #     "ftp_path": "/home/sky/Data/YU/huaruan/img/demo.jpeg"
#         # },
#         # {
#         #     "identifyType": ["道路-积水"],
#         #     "ftp_path": "/home/sky/Data/YU/huaruan/img/demo.jpeg"
#         # },
#         # {
#         #     "identifyType": ["道路-积水"],
#         #     "ftp_path": "/home/sky/Data/YU/huaruan/img/demo.jpeg"
#         # },
#         # {
#         #     "identifyType": ["道路-积水"],
#         #     "ftp_path": "/home/sky/Data/YU/huaruan/img/demo.jpeg"
#         # },
#         # {
#         #     "identifyType": ["道路-积水"],
#         #     "ftp_path": "/home/sky/Data/YU/huaruan/img/demo.jpeg"
#         # },
#         # {
#         #     "identifyType": ["道路-积水"],
#         #     "ftp_path": "/home/sky/Data/YU/huaruan/img/demo.jpeg"
#         # },
#         # {
#         #     "identifyType": ["道路-积水"],
#         #     "ftp_path": "/home/sky/Data/YU/huaruan/img/demo.jpeg"
#         # }
#     ]
#     payload =  tasks

#     # 打印要发送的内容
#     print("������ 准备发送请求到：", url)
#     print("������ 请求体：")
#     print(json.dumps(payload, ensure_ascii=False, indent=2))

#     async with httpx.AsyncClient(timeout=600.0) as client:
#         try:
#             resp = await client.post(url, json=payload)

#             print("\n������ 已发送请求，等待响应...")

#             if resp.status_code == 200:
#                 result = resp.json()
#                 print("\n✅ 批量识别结果：")
#                 print(json.dumps(result, ensure_ascii=False, indent=2))
#             else:
#                 print(f"\n❌ 请求失败，状态码: {resp.status_code}")
#                 print("响应内容：", resp.text)
#         except httpx.RequestError as e:
#             print(f"\n������ 请求异常: {e}")

# if __name__ == "__main__":
#     asyncio.run(send_request())




# import requests
# import argparse
# import json  # 提前导入，避免在输出时临时导入

# def analyze_image(api_url, image_path, requirements):
#     """调用图像分析API，上传图片并获取结果"""
#     try:
#         # 先检查图片文件是否存在，提前报错更友好
#         import os
#         if not os.path.exists(image_path):
#             return {"status": "error", "message": f"图片文件不存在: {image_path}"}
        
#         # 构造multipart/form-data格式的数据
#         files = {
#             'image': open(image_path, 'rb')  # 以二进制形式读取图片
#         }
#         data = {
#             'requirements': requirements  # 分析要求文本
#         }
        
#         # 发送POST请求（设置超时时间，避免卡死）
#         response = requests.post(api_url, files=files, data=data, timeout=30)
#         response.raise_for_status()  # 非200状态码会抛出异常
        
#         return response.json()  # 返回JSON结果
#     except FileNotFoundError:
#         return {"status": "error", "message": f"图片文件不存在: {image_path}"}
#     except requests.exceptions.RequestException as e:
#         return {"status": "error", "message": f"请求失败: {str(e)}"}
#     finally:
#         # 确保文件关闭，避免资源泄漏
#         if 'files' in locals() and 'image' in files:
#             files['image'].close()

# def check_health(api_url):
#     """检查服务健康状态"""
#     try:
#         response = requests.get(f"{api_url}/health", timeout=10)
#         return response.json()
#     except requests.exceptions.RequestException as e:
#         return {"status": "error", "message": f"健康检查失败: {str(e)}"}

# if __name__ == "__main__":
#     # 解析命令行参数（删除 required=True，保留 default）
#     parser = argparse.ArgumentParser(description="Qwen2.5-VL 图像分析客户端")
#     parser.add_argument("--api-url", type=str, default="http://localhost:8000", 
#                         help="API服务地址（如 http://localhost:8000）")
#     parser.add_argument("--image", type=str, default="/app/img/demo.jpeg",  # 无 required=True
#                         help="本地图片路径（默认：/app/img/demo.jpeg）")
#     parser.add_argument("--requirements", type=str, default="图中有什么",  # 无 required=True
#                         help="分析要求（默认：图中有什么）")
    
#     args = parser.parse_args()
    
#     # 1. 先检查服务健康状态
#     print("="*50)
#     print("������ 服务健康状态检查...")
#     health_status = check_health(args.api_url)
#     print("服务状态:", json.dumps(health_status, ensure_ascii=False, indent=2))
#     if health_status.get("status") != "healthy":
#         print("❌ 服务未就绪，退出程序")
#         exit(1)
    
#     # 2. 调用分析接口
#     print("\n" + "="*50)
#     print(f"������ 正在发送请求...")
#     print(f"图片路径: {args.image}")
#     print(f"分析要求: {args.requirements}")
#     result = analyze_image(f"{args.api_url}/analyze", args.image, args.requirements)
    
#     # 3. 格式化输出结果
#     print("\n" + "="*50)
#     print("������ 分析结果:")
#     print(json.dumps(result, ensure_ascii=False, indent=2))
#     print("="*50)


import asyncio
import json
import httpx

async def send_single_request():
    """发送单次请求的函数"""
    url = "http://127.0.0.1:5000/vision_engine/image_analysis"
    # url = "http://127.0.0.1:5000/vision_engine/image_analysis_sync"
    # 构造任务列表（可按需替换路径）
    tasks = [
        {
            "identifyType": ["道路-树木倒伏"],
            "ftp_path": "/home/lenovo/Zzyq/img/DJI_20251017152549_0001_WIDE.jpg"
        }
    ]
    payload = tasks

    # 打印要发送的内容（可选，循环100次可能会输出过多，可注释）
    # print("������ 准备发送请求到：", url)
    # print("������ 请求体：")
    # print(json.dumps(payload, ensure_ascii=False, indent=2))

    async with httpx.AsyncClient(timeout=600.0) as client:
        try:
            resp = await client.post(url, json=payload)

            # print("\n 已发送请求，等待响应...")

            if resp.status_code == 200:
                result = resp.json()
                print("\n✅ 批量识别结果：")
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print(f"\n❌ 请求失败，状态码: {resp.status_code}")
                print("响应内容：", resp.text)
        except httpx.RequestError as e:
            print(f"\n请求异常: {e}")

async def send_requests_repeatedly(count=100):
    """循环执行指定次数的请求"""
    for i in range(count):
        print(f"\n===== 第 {i+1} 次请求 =====")
        await send_single_request()  # 每次请求完成后再执行下一次

if __name__ == "__main__":
    asyncio.run(send_requests_repeatedly(1))  # 循环100次