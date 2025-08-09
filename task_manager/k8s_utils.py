import logging
import time
from kubernetes import client, stream, config
from fastapi.exceptions import HTTPException
import os
import re


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
        Yields each line of stdout and stderr as a dict.
        """
        try:
            # Get the pod name (assuming the pod name starts with the worker_name)
            pods = self.k8s_client.core_v1.list_namespaced_pod(
                namespace, label_selector=f"prefix={prefix}"
            )
            if not pods.items:
                yield {
                    "status": "error",
                    "exit_code": 1,
                    "stdout": "",
                    "stderr": f"No pods found for worker '{prefix}' in namespace '{namespace}'"
                }
                return

            pod_name = pods.items[0].metadata.name

            # Create a wrapper script that captures exit code more reliably
            # Use a temporary file approach to ensure exit code is captured
            modified_script = f"""
#!/bin/sh
# Execute the original script and capture its exit code
{script}
SCRIPT_EXIT_CODE=$?

# Always output the exit code to stderr (this will be captured)
echo "EXIT_CODE:$SCRIPT_EXIT_CODE" >&2

# Exit with the same code
exit $SCRIPT_EXIT_CODE
"""

            exec_response = stream.stream(
                self.k8s_client.core_v1.connect_get_namespaced_pod_exec,
                name=pod_name,
                namespace=namespace,
                command=["/bin/sh", "-c", modified_script],
                stderr=True,
                stdin=False,
                stdout=True,
                tty=False,
                _preload_content=False
            )

            # Read from the stream and yield lines as they arrive
            try:
                exit_code = 0  # Default to success
                stdout_lines = []
                stderr_lines = []
                exit_code_found = False
                
                # Simple approach: just read all data at once
                while exec_response.is_open():
                    exec_response.update(timeout=1)
                    
                    # Try to read any available data
                    try:
                        if exec_response.peek_stdout():
                            stdout_data = exec_response.read_stdout()
                            if stdout_data:
                                # Split by newlines and yield each line
                                lines = stdout_data.split('\n')
                                for line in lines:
                                    if line.strip():
                                        stdout_lines.append(line.strip())
                                        yield {
                                            "status": "running",
                                            "exit_code": None,
                                            "stdout": line.strip(),
                                            "stderr": ""
                                        }
                    except Exception as e:
                        pass
                    
                    try:
                        if exec_response.peek_stderr():
                            stderr_data = exec_response.read_stderr()
                            if stderr_data:
                                # Split by newlines and yield each line
                                lines = stderr_data.split('\n')
                                for line in lines:
                                    if line.startswith('EXIT_CODE:'):
                                        try:
                                            exit_code = int(line.split(':', 1)[1])
                                            exit_code_found = True
                                        except (ValueError, IndexError):
                                            exit_code = 0
                                    elif line.strip():
                                        stderr_lines.append(line.strip())
                                        yield {
                                            "status": "running",
                                            "exit_code": None,
                                            "stdout": "",
                                            "stderr": line.strip()
                                        }
                    except Exception as e:
                        pass
                
                # After stream closes, send final status with exit code
                status = "completed" if exit_code == 0 else "error"
                yield {
                    "status": status,
                    "exit_code": exit_code,
                    "stdout": "",
                    "stderr": ""
                }
            finally:
                exec_response.close()

        except Exception as e:
            # Try to get exit code from the error message or use default
            exit_code = 1  # Default error exit code
            if "exit code" in str(e).lower():
                try:
                    match = re.search(r'exit code[:\s]*(\d+)', str(e), re.IGNORECASE)
                    if match:
                        exit_code = int(match.group(1))
                except (ValueError, IndexError):
                    pass
            
            yield {
                "status": "error",
                "exit_code": exit_code,
                "stdout": "",
                "stderr": str(e)
            }