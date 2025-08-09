import asyncio
import time
from typing import AsyncGenerator
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json
from k8s_utils import K8sApplication

# Task Manager API with auto-reload support
app = FastAPI(title="Task Manager API", description="API for managing and executing tasks on Kubernetes")

class LogRequest(BaseModel):
    count: int = 10
    delay: float = 1.0

class K8sLogRequest(BaseModel):
    command: str
    namespace: str
    prefix: str

class HealthCheckRequest(BaseModel):
    interval: float = 1.0
    max_checks: int = 10

async def health_check_sse_generate_loop(interval: float = 1.0, max_checks: int = 10) -> AsyncGenerator[str, None]:
    """
    Async generator that yields health check status with specified interval
    """
    for i in range(max_checks):
        await asyncio.sleep(interval)
        health_status = {
            "timestamp": time.time(),
            "level": "INFO",
            "data": {
                "check_number": i + 1,
                "total_checks": max_checks,
                "status": "healthy",
                "interval": interval
            }
        }
        yield f"data: {json.dumps(health_status)}\n\n"

async def run_script_v2(command: str, namespace: str, prefix: str) -> AsyncGenerator[str, None]:
    """
    Execute script on Kubernetes pod and stream results with line-by-line buffering
    """
    try:
        # Create a mock session and data for K8sApplication
        session = {"user_id": "task_manager"}
        data = {"tenant_namespace": namespace}
        
        # Initialize K8sApplication
        k8s_app = K8sApplication("", data, session)
        
        # Execute command on pod and stream results
        for result in k8s_app.run_task_on_pod_v2(prefix, namespace, command):
            if result and isinstance(result, dict):
                # Check if this is an error result
                if result.get("status") == "error":
                    log_entry = {
                        "timestamp": time.time(),
                        "level": "ERROR",
                        "data": {
                            "error": result.get("stderr", ""),
                            "exit_code": result.get("exit_code", 1),
                            "namespace": namespace,
                            "prefix": prefix,
                            "command": command
                        }
                    }
                    yield f"data: {json.dumps(log_entry)}\n\n"
                else:
                    # Handle stdout - send each line immediately as it comes
                    if result.get("stdout"):
                        log_entry = {
                            "timestamp": time.time(),
                            "level": "INFO",
                            "data": {
                                "stdout": result.get("stdout", ""),
                                "stderr": "",
                                "exit_code": result.get("exit_code", 0),
                                "namespace": namespace,
                                "prefix": prefix,
                                "command": command
                            }
                        }
                        yield f"data: {json.dumps(log_entry)}\n\n"
                    
                    # Handle stderr - send each line immediately as it comes
                    if result.get("stderr"):
                        log_entry = {
                            "timestamp": time.time(),
                            "level": "INFO",
                            "data": {
                                "stdout": "",
                                "stderr": result.get("stderr", ""),
                                "exit_code": result.get("exit_code", 0),
                                "namespace": namespace,
                                "prefix": prefix,
                                "command": command
                            }
                        }
                        yield f"data: {json.dumps(log_entry)}\n\n"
                    
                    # Handle completion status
                    if result.get("status") == "completed":
                        log_entry = {
                            "timestamp": time.time(),
                            "level": "INFO",
                            "data": {
                                "stdout": "",
                                "stderr": "",
                                "exit_code": result.get("exit_code", 0),
                                "namespace": namespace,
                                "prefix": prefix,
                                "command": command,
                                "status": "completed"
                            }
                        }
                        yield f"data: {json.dumps(log_entry)}\n\n"
                
    except Exception as e:
        error_entry = {
            "timestamp": time.time(),
            "level": "ERROR",
            "data": {
                "error": str(e),
                "namespace": namespace,
                "prefix": prefix,
                "command": command
            }
        }
        yield f"data: {json.dumps(error_entry)}\n\n"

@app.get("/")
async def root():
    return {"message": "Task Manager API - Use /health for health checks or /execute for script execution"}

@app.post("/health")
async def health_check_sse(request: HealthCheckRequest):
    """
    Health check endpoint with SSE streaming
    """
    if request.interval < 0.1 or request.interval > 10:
        raise HTTPException(status_code=400, detail="Interval must be between 0.1 and 10 seconds")
    
    if request.max_checks < 1 or request.max_checks > 100:
        raise HTTPException(status_code=400, detail="Max checks must be between 1 and 100")
    
    return StreamingResponse(
        health_check_sse_generate_loop(request.interval, request.max_checks),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream"
        }
    )

@app.post("/execute")
async def execute_script(request: K8sLogRequest):
    """
    Execute script on Kubernetes pod with SSE streaming
    """
    if not request.command:
        raise HTTPException(status_code=400, detail="Command is required")
    
    if not request.namespace:
        raise HTTPException(status_code=400, detail="Namespace is required")
    
    if not request.prefix:
        raise HTTPException(status_code=400, detail="Prefix is required")
    
    return StreamingResponse(
        run_script_v2(request.command, request.namespace, request.prefix),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream"
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
