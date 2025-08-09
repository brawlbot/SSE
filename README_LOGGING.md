# Line-by-Line Logging with Kubernetes Utils

This document describes the enhanced line-by-line logging functionality implemented in `task_manager/k8s_utils.py`.

## Overview

The line-by-line logging system provides real-time streaming of logs from Kubernetes pods, task execution output, and filtered log processing. It's designed to be memory-efficient and provide immediate access to log data without waiting for complete execution.

## Key Features

- **Real-time streaming**: Logs are processed and yielded as they arrive
- **Line-by-line processing**: Each log line is processed individually with metadata
- **Timestamp tracking**: Automatic timestamp parsing and tracking for each log entry
- **Status monitoring**: Real-time status updates throughout the logging process
- **Error handling**: Comprehensive error handling with detailed error messages
- **Memory efficient**: No buffering of entire log files in memory
- **Flexible filtering**: Support for regex pattern filtering and line limits

## Methods Overview

### 1. `get_pod_logs_line_by_line()`

Streams logs from a Kubernetes pod in real-time.

```python
def get_pod_logs_line_by_line(self, pod_name: str, namespace: str, container: str = None, 
                             tail_lines: int = None, follow: bool = True):
```

**Parameters:**
- `pod_name`: Name of the target pod
- `namespace`: Kubernetes namespace
- `container`: Container name (for multi-container pods)
- `tail_lines`: Number of lines to tail from the end
- `follow`: Whether to follow logs continuously

**Returns:** Generator yielding log lines with metadata

**Example:**
```python
for log_line in k8s_app.get_pod_logs_line_by_line('my-app-pod', 'default'):
    if log_line['status'] == 'streaming':
        print(f"[{log_line['timestamp']}] {log_line['log_line']}")
    elif log_line['status'] == 'completed':
        print(f"Log streaming completed: {log_line['message']}")
```

### 2. `get_pod_logs_with_filter()`

Retrieves and filters logs from a pod with pattern matching.

```python
def get_pod_logs_with_filter(self, pod_name: str, namespace: str, container: str = None,
                            filter_pattern: str = None, max_lines: int = 1000):
```

**Parameters:**
- `pod_name`: Name of the target pod
- `namespace`: Kubernetes namespace
- `container`: Container name (for multi-container pods)
- `filter_pattern`: Regex pattern for filtering log lines
- `max_lines`: Maximum number of lines to return

**Returns:** Generator yielding filtered log lines with metadata

**Example:**
```python
for log_line in k8s_app.get_pod_logs_with_filter(
    'my-app-pod', 'default', filter_pattern='ERROR', max_lines=1000
):
    if log_line['status'] == 'filtered':
        print(f"Error: {log_line['log_line']}")
```

### 3. `run_task_on_pod_v2()`

Executes tasks on pods with real-time output streaming.

```python
def run_task_on_pod_v2(self, prefix: str, namespace: str, script: str):
```

**Parameters:**
- `prefix`: Worker pod prefix for identification
- `namespace`: Kubernetes namespace
- `script`: Shell script to execute

**Returns:** Generator yielding real-time task output

**Example:**
```python
for output in k8s_app.run_task_on_pod_v2('worker', 'default', 'echo "Hello World"'):
    if output['stdout']:
        print(f"STDOUT: {output['stdout']}")
    elif output['stderr']:
        print(f"STDERR: {output['stderr']}")
    elif output['status'] == 'completed':
        print(f"Task completed: {output['message']}")
```

## Output Format

All methods return dictionaries with the following structure:

### Log Line Output
```python
{
    "log_line": "Actual log content",
    "timestamp": 1705312215.123456,  # Unix timestamp
    "pod_name": "my-app-pod",
    "namespace": "default",
    "container": "app-container",
    "status": "streaming|filtered|completed|error",
    "line_number": 42,  # Only for filtered logs
    "message": "Additional status message"  # For completion/error
}
```

### Task Output
```python
{
    "stdout": "Standard output content",
    "stderr": "Standard error content",
    "exit_code": 0,
    "status": "running|completed|error",
    "timestamp": 1705312215.123456,
    "message": "Status message"
}
```

## Usage Examples

### Real-time Log Monitoring
```python
from task_manager.k8s_utils import K8sApplication

# Initialize
k8s_app = K8sApplication("templates", {}, {})

# Stream logs in real-time
for log_line in k8s_app.get_pod_logs_line_by_line('my-app', 'default'):
    if log_line['status'] == 'streaming':
        print(f"[{log_line['timestamp']}] {log_line['log_line']}")
    elif log_line['status'] == 'error':
        print(f"Error: {log_line['message']}")
        break
```

### Error Log Filtering
```python
# Filter for error messages only
error_count = 0
for log_line in k8s_app.get_pod_logs_with_filter(
    'my-app', 'default', filter_pattern='ERROR|FATAL', max_lines=500
):
    if log_line['status'] == 'filtered':
        error_count += 1
        print(f"Error {error_count}: {log_line['log_line']}")
    elif log_line['status'] == 'completed':
        print(f"Found {error_count} error messages")
```

### Task Execution with Streaming
```python
# Execute a long-running task with real-time output
script = """
echo "Starting deployment..."
sleep 5
echo "Deployment completed"
"""

for output in k8s_app.run_task_on_pod_v2('worker', 'default', script):
    if output['stdout']:
        print(f"STDOUT: {output['stdout']}")
    elif output['stderr']:
        print(f"STDERR: {output['stderr']}")
    elif output['status'] == 'completed':
        print("Task completed successfully")
```

### Multi-pod Log Aggregation
```python
def aggregate_logs(pod_names, namespace):
    """Aggregate logs from multiple pods"""
    all_logs = []
    
    for pod_name in pod_names:
        pod_logs = k8s_app.get_pod_logs_with_filter(
            pod_name, namespace, max_lines=100
        )
        
        for log_line in pod_logs:
            if log_line['status'] == 'filtered':
                all_logs.append({
                    'pod': pod_name,
                    'timestamp': log_line['timestamp'],
                    'message': log_line['log_line']
                })
    
    return sorted(all_logs, key=lambda x: x['timestamp'])

# Usage
logs = aggregate_logs(['app-1', 'app-2', 'app-3'], 'default')
for log in logs:
    print(f"[{log['timestamp']}] {log['pod']}: {log['message']}")
```

## Error Handling

The system provides comprehensive error handling:

- **Connection errors**: Kubernetes API connection failures
- **Pod not found**: Missing or inaccessible pods
- **Container errors**: Multi-container pod issues
- **Permission errors**: RBAC and access control issues
- **Network errors**: Timeout and connectivity issues

Each error includes:
- Error message
- Timestamp
- Pod and namespace context
- Suggested resolution steps

## Performance Considerations

- **Memory usage**: Minimal memory footprint due to streaming
- **Network efficiency**: Real-time processing reduces latency
- **Scalability**: Handles large log files without memory issues
- **Concurrency**: Safe for concurrent access from multiple threads

## Best Practices

1. **Always check status**: Verify the status field before processing output
2. **Handle errors gracefully**: Implement proper error handling for production use
3. **Use timeouts**: Implement appropriate timeouts for long-running operations
4. **Monitor resources**: Be aware of Kubernetes API rate limits
5. **Log rotation**: Consider log rotation policies for long-running streams

## Troubleshooting

### Common Issues

1. **No logs appearing**: Check pod status and container names
2. **Permission denied**: Verify RBAC permissions and service account
3. **Connection timeout**: Check network connectivity and API server status
4. **Empty output**: Verify log generation and container configuration

### Debug Mode

Enable debug logging to troubleshoot issues:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Dependencies

- `kubernetes`: Official Kubernetes Python client
- `fastapi`: Web framework for HTTP exceptions
- `datetime`: Timestamp parsing and formatting
- `re`: Regular expression support for filtering

## Testing

Run the test scripts to verify functionality:

```bash
python3 test_logging.py
python3 example_logging_usage.py
```

## Support

For issues or questions:
1. Check the error messages for specific details
2. Verify Kubernetes cluster connectivity
3. Review pod and namespace configurations
4. Check RBAC permissions and service accounts
