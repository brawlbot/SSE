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
                    "message": f"No pods found for worker '{prefix}' in namespace '{namespace}'",
                    "stdout": "",
                    "stderr": f"No pods found for worker '{prefix}' in namespace '{namespace}'"
                }
                return

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
                _preload_content=False
            )

            # Read from the stream and yield lines as they arrive
            try:
                while exec_response.is_open():
                    exec_response.update(timeout=1)
                    while exec_response.peek_stdout():
                        stdout_data = exec_response.read_stdout()
                        if stdout_data:
                            for line in stdout_data.splitlines(keepends=True):
                                yield {
                                    "status": "running",
                                    "exit_code": None,
                                    "message": "",
                                    "stdout": line,
                                    "stderr": ""
                                }
                    while exec_response.peek_stderr():
                        stderr_data = exec_response.read_stderr()
                        if stderr_data:
                            for line in stderr_data.splitlines(keepends=True):
                                yield {
                                    "status": "running",
                                    "exit_code": None,
                                    "message": "",
                                    "stdout": "",
                                    "stderr": line
                                }
                # After stream closes, get exit code if available
                exit_code = exec_response.returncode if hasattr(exec_response, 'returncode') else 0
                status = "success" if exit_code == 0 else "error"
                yield {
                    "status": status,
                    "exit_code": exit_code,
                    "message": f"Task executed on worker '{prefix}' with exit code {exit_code}",
                    "stdout": "",
                    "stderr": ""
                }
            finally:
                exec_response.close()

        except Exception as e:
            yield {
                "status": "error",
                "exit_code": 1,
                "message": f"Failed to execute task on worker: {str(e)}",
                "stdout": "",
                "stderr": str(e)
            }