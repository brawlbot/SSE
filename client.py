import asyncio
import aiohttp
import json
from datetime import datetime

class ClientSSE:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def _get_session(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def health_check(self, interval: float = 1.0, max_checks: int = 10):
        """
        Perform health check with SSE streaming
        
        Args:
            interval (float): Time between health checks
            max_checks (int): Maximum number of health checks
        """
        session = await self._get_session()
        return await self._stream_health_check(session, interval, max_checks)
    
    async def execute_script(self, command: str, namespace: str, prefix: str):
        """
        Execute script on Kubernetes pod with SSE streaming
        
        Args:
            command (str): Command to execute on the pod
            namespace (str): Kubernetes namespace
            prefix (str): Pod prefix/label selector
        """
        session = await self._get_session()
        return await self._stream_script_execution(session, command, namespace, prefix)
    
    async def _stream_health_check(self, session, interval: float, max_checks: int):
        """
        Stream health check results from the SSE endpoint
        """
        payload = {
            "interval": interval,
            "max_checks": max_checks
        }
        
        async with session.post(f'{self.base_url}/health', json=payload) as response:
            if response.status == 200:
                async for line in response.content:
                    line = line.decode('utf-8').strip()
                    if line.startswith('data: '):
                        try:
                            log_data = json.loads(line[6:])
                            timestamp = datetime.fromtimestamp(log_data['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
                            print(f"[{timestamp}] {log_data['level']}: {log_data['message']} (check: {log_data['data']['check_number']}/{log_data['data']['total_checks']})")
                        except json.JSONDecodeError as e:
                            print(f"Error parsing JSON: {e}")
            else:
                print(f"Error: {response.status}")
    
    async def _stream_script_execution(self, session, command: str, namespace: str, prefix: str):
        """
        Stream script execution results from the SSE endpoint
        """
        payload = {
            "command": command,
            "namespace": namespace,
            "prefix": prefix
        }
        
        async with session.post(f'{self.base_url}/execute', json=payload) as response:
            if response.status == 200:
                async for line in response.content:
                    line = line.decode('utf-8').strip()
                    if line.startswith('data: '):
                        try:
                            log_data = json.loads(line[6:])
                            timestamp = datetime.fromtimestamp(log_data['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
                            
                            if log_data['level'] == 'ERROR':
                                print(f"[{timestamp}] ERROR: {log_data['message']}")
                                if 'error' in log_data['data']:
                                    print(f"  Details: {log_data['data']['error']}")
                            else:
                                print(f"[{timestamp}] {log_data['level']}: {log_data['message']}")
                                if 'stdout' in log_data['data'] and log_data['data']['stdout']:
                                    print(f"  STDOUT: {log_data['data']['stdout']}")
                                if 'stderr' in log_data['data'] and log_data['data']['stderr']:
                                    print(f"  STDERR: {log_data['data']['stderr']}")
                                if 'exit_code' in log_data['data']:
                                    print(f"  Exit Code: {log_data['data']['exit_code']}")
                                    
                        except json.JSONDecodeError as e:
                            print(f"Error parsing JSON: {e}")
            else:
                print(f"Error: {response.status}")
    
    async def close(self):
        """
        Close the session
        """
        if self.session:
            await self.session.close()
            self.session = None

# Legacy functions for backward compatibility
async def health_check_example():
    """
    Example client that performs health checks
    """
    async with ClientSSE() as client:
        print("Performing health check...")
        await client.health_check(interval=0.5, max_checks=5)

async def script_execution_example():
    """
    Example client that executes scripts on Kubernetes
    """
    async with ClientSSE() as client:
        print("Executing script on Kubernetes...")
        command = "echo 'Hello from K8s pod' && date"
        namespace = "dbext-resources"
        prefix = "sh6itcgl"
        await client.execute_script(command, namespace, prefix)

if __name__ == "__main__":
    print("Task Manager API Client Example")
    print("Make sure the server is running on http://localhost:8000")
    print("=" * 50)
    
    # Run the examples
    # asyncio.run(health_check_example())
    asyncio.run(script_execution_example())
