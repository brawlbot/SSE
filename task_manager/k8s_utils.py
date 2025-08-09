import logging
import time
from kubernetes import client, stream, config
from fastapi.exceptions import HTTPException
import os


class K8sClient:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(K8sClient, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        logging.info("Initializing Kubernetes client...")
        try:
            # Load the Kubernetes configuration
            config.load_kube_config()
            logging.info("Kubernetes configuration loaded successfully")
            
            # Create API clients after loading config
            self.apps_v1 = client.AppsV1Api()
            self.core_v1 = client.CoreV1Api()
            self.api_client = client.ApiClient()
            self.networking_v1 = client.NetworkingV1Api()
            self.namespace = "default"
            logging.info("Kubernetes API clients initialized successfully")
        except Exception as e:
            logging.error(f"Failed to initialize Kubernetes client: {str(e)}")
            raise HTTPException(
                status_code=500, detail="Failed to initialize Kubernetes client"
            )


class K8sApplication:
    def __init__(self, template_folder: str, data: dict, session: dict):
        self.session = session
        self.data = data
        self.k8s_client = K8sClient()
        self.template_folder = template_folder

    def run_task_on_pod_v2(self, prefix: str, namespace: str, script: str):
        """
        Run a task script on a worker pod with real-time line-by-line streaming.
        """
        try:
            # Get the pod name (assuming the pod name starts with the worker_name)
            pods = self.k8s_client.core_v1.list_namespaced_pod(
                namespace, label_selector=f"prefix={prefix}"
            )
            if not pods.items:
                raise Exception(
                    f"No pods found for worker '{prefix}' in namespace '{namespace}'"
                )

            pod_name = pods.items[0].metadata.name

            command = ["/bin/sh", "-c", script]

            # Execute the command inside the pod
            exec_response = stream.stream(
                self.k8s_client.core_v1.connect_get_namespaced_pod_exec,
                name=pod_name,
                namespace=namespace,
                command=command,
                stderr=True,
                stdin=False,
                stdout=True,
                tty=False,
            )

            # Buffers for incomplete lines
            stdout_buffer = ""
            stderr_buffer = ""
            
            # Process output in real-time, line by line
            for chunk in exec_response:
                if hasattr(chunk, 'stdout') and chunk.stdout:
                    stdout_buffer += chunk.stdout
                    
                    # Process complete lines from stdout
                    while '\n' in stdout_buffer:
                        line, stdout_buffer = stdout_buffer.split('\n', 1)
                        if line.strip():  # Only yield non-empty lines
                            yield {
                                "stdout": line,
                                "stderr": "",
                                "exit_code": 0,
                                "status": "running",
                                "timestamp": time.time()
                            }
                    
                elif hasattr(chunk, 'stderr') and chunk.stderr:
                    stderr_buffer += chunk.stderr
                    
                    # Process complete lines from stderr
                    while '\n' in stderr_buffer:
                        line, stderr_buffer = stderr_buffer.split('\n', 1)
                        if line.strip():  # Only yield non-empty lines
                            yield {
                                "stdout": "",
                                "stderr": line,
                                "exit_code": 0,
                                "status": "running",
                                "timestamp": time.time()
                            }
                    
                else:
                    # Handle case where chunk might not have expected attributes
                    if chunk:
                        yield {
                            "stdout": str(chunk) if chunk else "",
                            "stderr": "",
                            "exit_code": 0,
                            "status": "running",
                            "timestamp": time.time()
                        }
            
            # Process any remaining content in buffers
            if stdout_buffer.strip():
                yield {
                    "stdout": stdout_buffer.strip(),
                    "stderr": "",
                    "exit_code": 0,
                    "status": "completed",
                    "timestamp": time.time()
                }
                
            if stderr_buffer.strip():
                yield {
                    "stdout": "",
                    "stderr": stderr_buffer.strip(),
                    "exit_code": 0,
                    "status": "completed",
                    "timestamp": time.time()
                }
            
            # Final completion message
            yield {
                "stdout": "",
                "stderr": "",
                "exit_code": 0,
                "status": "completed",
                "timestamp": time.time(),
                "message": "Task execution completed successfully"
            }

        except Exception as e:
            # Yield error information
            yield {
                "stdout": "",
                "stderr": str(e),
                "exit_code": -1,
                "status": "error",
                "timestamp": time.time(),
                "message": f"Failed to execute task on worker: {str(e)}"
            }
