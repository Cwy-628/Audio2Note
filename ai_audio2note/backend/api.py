"""
FastAPI Backend for AI Audio2Note
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import uvicorn
import os

from .services.audio_downloader import AudioDownloader
from .services.process_service import ProcessService

# 创建FastAPI应用
app = FastAPI(
    title="AI Audio2Note API",
    description="视频下载和音频提取API",
    version="1.0.0"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化服务
process_service = ProcessService()

# Pydantic模型
class VideoProcessRequest(BaseModel):
    url: str
    page_number: Optional[int] = None
    download_dir: Optional[str] = None

class VideoProcessResponse(BaseModel):
    success: bool
    files: Optional[List[str]] = None
    session_folder: Optional[str] = None
    video_title: Optional[str] = None
    error: Optional[str] = None

# API路由
@app.get("/")
async def root():
    return {"message": "AI Audio2Note API is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/api/process/video", response_model=VideoProcessResponse)
async def process_video(request: VideoProcessRequest):
    """
    视频下载接口：接收视频 URL，调用服务层进行下载
    """
    print(f"收到视频处理请求: {request.url}")
    
    if not request.url or len(request.url.strip()) < 10:
        print("URL验证失败")
        raise HTTPException(status_code=400, detail="Invalid URL")
    
    try:
        print("开始处理视频...")
        print(f"请求参数: url={request.url}, page_number={request.page_number}, download_dir={request.download_dir}")
        
        # 如果指定了下载目录，创建新的服务实例
        if request.download_dir:
            print(f"使用自定义下载目录: {request.download_dir}")
            # 验证目录是否存在且可写
            if not os.path.exists(request.download_dir):
                print(f"目录不存在，尝试创建: {request.download_dir}")
                try:
                    os.makedirs(request.download_dir, exist_ok=True)
                    print("目录创建成功")
                except Exception as e:
                    print(f"目录创建失败: {e}")
                    raise HTTPException(status_code=400, detail=f"无法创建下载目录: {str(e)}")
            
            service = ProcessService(request.download_dir)
        else:
            print("使用默认下载目录")
            service = process_service
            
        result = service.process_video(
            url=request.url, 
            page_number=request.page_number
        )
        print(f"处理结果: {result}")
        
        if result.get("success"):
            return VideoProcessResponse(**result)
        else:
            error_msg = result.get("error", "Unknown error")
            print(f"处理失败: {error_msg}")
            raise HTTPException(status_code=500, detail=error_msg)
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"处理异常: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
