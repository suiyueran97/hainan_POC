import os
import asyncio
import logging
import uuid
import json
from datetime import datetime
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from typing import List, Dict
import httpx  # 异步 HTTP 客户端

from main_async import process_batch_tasks_async


# ============================
# 日志配置
# ============================
LOG_DIR = "./logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "server.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================
# 常量配置
# ============================
TASK_STATUS_PENDING = "pending"
TASK_STATUS_PROCESSING = "processing"
TASK_STATUS_DONE = "done"
TASK_STATUS_FAILED = "failed"

# 回调推送配置
CALLBACK_URL = os.environ.get("CALLBACK_URL", "http://127.0.0.1:9806/patrol/v1/piTaskImg/imgCallback")
# CALLBACK_URL = os.environ.get("CALLBACK_URL", "http://127.0.0.1:29806/patrol/v1/piTaskImg/imgCallback")

# 失败推送记录文件
FAILED_PUSH_FILE = Path("./failed_push.json")

# ============================
# 内存任务存储
# ============================
task_queue = asyncio.Queue(maxsize=100000)
task_status = dict()
task_metadata = dict()

# ============================
# 任务持久化目录
# ============================
TASK_DATA_DIR = Path("./task_data")
TASK_DATA_DIR.mkdir(exist_ok=True)

# ============================
# 数据模型定义
# ============================
class TaskItem(BaseModel):
    identifyType: List[str]
    ftp_path: str


class TaskResponseItem(BaseModel):
    ftpPath: str
    judgmentInfo: List[Dict]
    status: str
    error_msg: str

# 同步测试结构
class TaskResponseItem2(BaseModel):
    ftp_path: str
    judgmentInfo: List[Dict]
    status: str
    error_msg: str

# ============================
# 工具函数：任务持久化
# ============================
def save_task_to_disk(task_id, data):
    with open(TASK_DATA_DIR / f"{task_id}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_tasks_from_disk():
    for file in TASK_DATA_DIR.glob("*.json"):
        task_id = file.stem
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
            task_status[task_id] = data["status_info"]
            task_metadata[task_id] = data["metadata"]
            if data["status_info"]["status"] in [TASK_STATUS_PENDING, TASK_STATUS_PROCESSING]:
                asyncio.create_task(task_queue.put(task_id))
            logger.info(f"恢复任务: {task_id} ({data['status_info']['status']})")
        except Exception as e:
            logger.error(f"恢复任务 {task_id} 失败: {e}")


# ============================
# 工具函数：推送结果（带重试）
# ============================
async def push_task_result(task_id: str, data: dict, max_retries: int = 3):
    retry_delay = 2
    for attempt in range(1, max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(CALLBACK_URL, json=data)
                if resp.status_code == 200:
                    logger.info(f"✅ 成功推送任务结果: {task_id} (第 {attempt} 次尝试)")
                    return
                else:
                    logger.warning(f"⚠️ 推送失败 {task_id} (第 {attempt} 次)，状态码: {resp.status_code}，响应: {resp.text}")
        except Exception as e:
            logger.error(f"❌ 推送异常 {task_id} (第 {attempt} 次): {e}")
        await asyncio.sleep(retry_delay)
        retry_delay *= 2
    record_failed_push(task_id, data)


def record_failed_push(task_id: str, data: dict):
    failed_records = []
    if FAILED_PUSH_FILE.exists():
        try:
            with open(FAILED_PUSH_FILE, "r", encoding="utf-8") as f:
                failed_records = json.load(f)
        except Exception:
            failed_records = []
    failed_records.append({
        "task_id": task_id,
        "callback_url": CALLBACK_URL,
        "data": data,
        "time": datetime.now().isoformat()
    })
    with open(FAILED_PUSH_FILE, "w", encoding="utf-8") as f:
        json.dump(failed_records, f, ensure_ascii=False, indent=2)


# ============================
# 后台任务 Worker
# ============================
async def task_worker():
    """后台任务处理Worker"""
    while True:
        task_id = await task_queue.get()
        try:
            task_status[task_id]["status"] = TASK_STATUS_PROCESSING
            save_task_to_disk(task_id, {
                "status_info": task_status[task_id],
                "metadata": task_metadata[task_id]
            })

            tasks = task_metadata[task_id]
            tasks_as_dict = [task for task in tasks]

            logger.info(f"输入问题 :{tasks_as_dict} ")

            # 模型推理
            results = await process_batch_tasks_async(tasks_as_dict)

            # 构造推送结构
            # formatted_results = [
            #     TaskResponseItem(
            #         ftpPath=item["ftp_path"],
            #         judgmentInfo=item.get("judgmentInfo", []),
            #         # status="success",
            #         s = 'results.status'
            #         # error_msg=""
            #         er = 'results.error_msg'
            #     ).model_dump()
            #     for item in results
            # ]
            formatted_results = [
                TaskResponseItem(
                    ftpPath=item["ftp_path"],
                    judgmentInfo=item.get("judgmentInfo", []),
                    status=item.get("status", "success"),  # 从结果项中获取状态，默认success
                    error_msg=item.get("error_msg", "")    # 从结果项中获取错误信息，默认空
                ).model_dump()
                for item in results
            ]


            task_status[task_id] = {
                "status": TASK_STATUS_DONE,
                "response": formatted_results,
                "create_time": task_status[task_id]["create_time"],
                "end_time": datetime.now().timestamp()
            }

            # 推送结果
            asyncio.create_task(push_task_result(task_id, {
                "taskId": task_id,
                "response": formatted_results
            }))
            logger.info(f"推送taskId :{task_id} , 推送response: {formatted_results}")

        except Exception as e:
            logger.exception(f"任务 {task_id} 执行失败: {e}")
            formatted_failed = [
                TaskResponseItem(
                    ftpPath=item["ftp_path"],
                    judgmentInfo=[],
                    status="failed",
                    error_msg=str(e)
                ).model_dump()
                for item in task_metadata[task_id]
            ]

            task_status[task_id] = {
                "status": TASK_STATUS_FAILED,
                "error": str(e),
                "create_time": task_status[task_id]["create_time"],
                "end_time": datetime.now().timestamp()
            }

            # 推送失败信息
            asyncio.create_task(push_task_result(task_id, {
                "taskId": task_id,
                "response": formatted_failed
            }))
            logger.info(f"推送taskId :{task_id} , 推送response: {formatted_results} ")

        finally:
            save_task_to_disk(task_id, {
                "status_info": task_status[task_id],
                "metadata": task_metadata[task_id]
            })
            task_queue.task_done()


# ============================
# FastAPI 生命周期管理
# ============================
@asynccontextmanager
async def lifespan(app: FastAPI):
    load_tasks_from_disk()
    
    worker_count = os.cpu_count() or 4
    for _ in range(worker_count):
        asyncio.create_task(task_worker())
    logger.info(f"✅ 启动 {worker_count} 个任务处理器成功")

    yield
    logger.info("FastAPI 服务关闭，执行清理逻辑中...")


# ============================
# 初始化应用
# ============================
app = FastAPI(lifespan=lifespan)


# ============================
# API 路由
# ============================
@app.post("/vision_engine/image_analysis")
async def submit_tasks(tasks: List[TaskItem]):

    task_id = str(uuid.uuid4())
    create_time = datetime.now().timestamp()

    task_status[task_id] = {"status": TASK_STATUS_PENDING, "create_time": create_time}
    task_metadata[task_id] = [t.model_dump() for t in tasks]

    save_task_to_disk(task_id, {"status_info": task_status[task_id], "metadata": task_metadata[task_id]})

    try:
        task_queue.put_nowait(task_id)
    except asyncio.QueueFull:
        del task_status[task_id]
        del task_metadata[task_id]
        raise HTTPException(status_code=503, detail="任务队列已满，请稍后再试")

    logger.info(f"任务提交成功: {task_id}（{len(tasks)} 个子任务）")
    return {
        "task_id": task_id,
        "status": TASK_STATUS_PENDING,
        "create_time": create_time,
        "task_count": len(tasks)
    }

@app.post("/vision_engine/image_analysis_sync", response_model=List[TaskResponseItem2])
async def analyze_images(request: Request, tasks: List[TaskItem]):
    """
    批量异步分析图像场景接口
    自动记录每次请求参数与处理结果到日志文件
    """

    # 记录请求数据
    request_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    logger.info(f"t同步收到请求 [{request_id}]：共 {len(tasks)} 个任务")

    try:
        # 转换任务为字典格式
        tasks_as_dict = [task.model_dump() for task in tasks]
        logger.info(f"[{request_id}] 同步请求参数: {tasks_as_dict}")

        # 异步调用模型处理
        results = await process_batch_tasks_async(tasks_as_dict)

        # 格式化结果为响应模型格式
        formatted_results = [
            TaskResponseItem2(
                ftp_path=item["ftp_path"],
                judgmentInfo=item.get("judgmentInfo", []),
                status=item.get("status", "success"),
                error_msg=item.get("error_msg", "")
            )
            for item in results
        ]

        # 记录响应结果
        logger.info(f"[{request_id}] 同步响应结果: {[r.model_dump() for r in formatted_results]}")

        return formatted_results
    except Exception as e:
        logger.exception(f"[{request_id}] 同步处理出错: {e}")
        # 异常时返回每个任务的失败信息
        error_results = [
            TaskResponseItem2(
                ftp_path=task.ftp_path,
                judgmentInfo=[],
                status="failed",
                error_msg=str(e)
            )
            for task in tasks
        ]
        return error_results
    


@app.get("/vision_engine/get_result/{task_id}")
async def get_result(task_id: str):
    if task_id not in task_status:
        raise HTTPException(status_code=404, detail="任务ID不存在")

    status_info = task_status[task_id].copy()
    return {
        "task_id": task_id,
        "status": status_info["status"],
        "create_time": status_info["create_time"],
        "end_time": status_info.get("end_time"),
        "result": status_info.get("result") if status_info["status"] == TASK_STATUS_DONE else None,
        "error": status_info.get("error") if status_info["status"] == TASK_STATUS_FAILED else None
    }


# ============================
# 主入口
# ============================
if __name__ == "__main__":
    import uvicorn
    logger.info("启动 FastAPI 服务...")
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("API_PORT", 5000)), workers=1)