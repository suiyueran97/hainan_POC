# main_async.py
import json
import os
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Tuple
from loguru import logger
from prompt_json import prompt
from model.model import run_inference  # 导入模型推理函数


# ==============================
# 1. 核心配置
# ==============================
PROMPT_MAP = prompt
VALID_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".tiff")
MAX_WORKERS = 4  # 并发线程数


# ==============================
# 2. 参数校验与结果解析
# ==============================
def validate_task_params(task: Dict) -> None:
    """校验输入任务的合法性"""
    required_fields = ["identifyType", "ftp_path"]
    for field in required_fields:
        if field not in task:
            raise ValueError(f"任务缺少必要字段：{field}")

    identify_types = task["identifyType"]
    if not isinstance(identify_types, list) or not identify_types:
        raise ValueError("identifyType必须是非空列表")

    invalid_types = [t for t in identify_types if t not in PROMPT_MAP]
    if invalid_types:
        raise ValueError(f"以下识别类型无对应Prompt：{', '.join(invalid_types)}")

    img_path = task["ftp_path"]
    if not os.path.exists(img_path):
        raise FileNotFoundError(f"图片路径不存在：{img_path}")
    if not os.path.isfile(img_path):
        raise IsADirectoryError(f"路径不是文件：{img_path}")
    if not img_path.lower().endswith(VALID_IMAGE_EXTS):
        raise ValueError(f"不支持的图片格式，仅支持：{VALID_IMAGE_EXTS}")


# def parse_model_answer(identify_type: str, model_answer: str) -> Dict:
#     """解析模型回答为结构化JSON"""
#     try:
#         formatted_answer = model_answer.replace("'", "\"")
#         parsed_answer = json.loads(formatted_answer)

#         result = parsed_answer[0]['状态']
#         desc = parsed_answer[0]['描述']
#         return {
#             "identifyType": identify_type,
#             "result": result,
#             "sceneDesc": desc
#         }
#     except Exception as e:
#         raise ValueError(f"模型返回结果解析失败: {e}\n原始内容: {model_answer}")
import re

def parse_model_answer(identify_type: str, model_answer: str) -> Dict:
    """解析模型回答为结构化JSON"""
    try:
        # 使用正则表达式提取JSON数组部分
        json_pattern = r'\[\s*\{.*?\}\s*\]'
        match = re.search(json_pattern, model_answer, re.DOTALL)
        if not match:
            raise ValueError("未找到符合格式的JSON内容")
        
        formatted_answer = match.group(0).replace("'", "\"")
        parsed_answer = json.loads(formatted_answer)

        result = parsed_answer[0]['状态']
        desc = parsed_answer[0]['描述']
        return {
            "identifyType": identify_type,
            "result": result,
            "sceneDesc": desc
        }
    except Exception as e:
        raise ValueError(f"模型返回结果解析失败: {e}\n原始内容: {model_answer}")


# ==============================
# 3. 单任务同步处理
# ==============================
def process_single_task_sync(task: Dict) -> Dict:
    """同步处理单个任务"""
    start_time = time.time()
    try:
        validate_task_params(task)
        img_path = task["ftp_path"]
        identify_types = task["identifyType"]

        judgment_info = []
        for type_name in identify_types:
            current_prompt = PROMPT_MAP[type_name]
            logger.info(f"开始识别【{type_name}】 -> {os.path.basename(img_path)}")

            model_answer = run_inference(
                image_path=img_path,
                question=current_prompt
            )
            print(model_answer)
            logger.debug(f"模型原始回答（前200字符）：{model_answer[:200]}")

            parsed = parse_model_answer(type_name, model_answer)
            judgment_info.append(parsed)

        elapsed = round(time.time() - start_time, 2)
        logger.info(f"任务完成 {os.path.basename(img_path)} ✅ 耗时 {elapsed}s")

        return {
            "ftp_path": img_path,
            "judgmentInfo": judgment_info,
            "status": "success",
            "error_msg": ""
        }

    except Exception as e:
        error_msg = str(e)
        logger.error(f"任务失败：{error_msg}")
        return {
            "ftp_path": task.get("ftp_path", "未知路径"),
            "judgmentInfo": [],
            "status": "failed",
            "error_msg": error_msg
        }


# ==============================
# 4. 异步包装
# ==============================
async def process_single_task_async(task: Dict, executor) -> Dict:
    """异步封装单任务"""
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        executor,
        process_single_task_sync,
        task,
    )
    return result


async def process_batch_tasks_async(
    tasks: List[Dict],
    max_workers: int = MAX_WORKERS
) -> List[Dict]:
    """批量异步任务处理入口"""
    total = len(tasks)
    logger.info(f"启动批量任务，共 {total} 个，最大并发：{max_workers}")
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        coroutines = [
            process_single_task_async(task, executor)
            for task in tasks
        ]
        results = await asyncio.gather(*coroutines)

    elapsed = round(time.time() - start_time, 2)
    success = sum(1 for r in results if r["status"] == "success")
    failed = total - success
    logger.info(f"✅ 批量任务完成：成功 {success} / 失败 {failed}，耗时 {elapsed}s")

    return results