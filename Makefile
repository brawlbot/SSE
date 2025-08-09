prefix = sh6itcgl
namespace = dbext-resources

.PHONY: help server dev client interface test-health test-execute clean

help:
	@echo "Task Manager Project - make server|dev|client|interface|test-health|test-execute|clean"

server:
	cd task_manager && python server.py

start:
	@echo "Starting server with auto-reload..."
	cd task_manager && uvicorn server:app --host 0.0.0.0 --port 8000 --reload --reload-dir .

stop:
	ps aux | grep "uvicorn server:app" | grep -v grep | awk '{print $$2}' | xargs kill -9

restart:
	make stop
	make start

client:
	python client.py

interface:
	python interface.py

test-health:
	@echo "Testing health endpoint..."
	@curl -s -N -X POST "http://localhost:8000/health" \
		-H "Content-Type: application/json" \
		-d '{"interval": 0.5, "max_checks": 3}' | head -10

test-execute:
	@echo "Testing execute endpoint..."
	@curl -s -N -X POST "http://localhost:8000/execute" \
		-H "Content-Type: application/json" \
		-d '{"command": "echo hello", "namespace": "$(namespace)", "prefix": "$(prefix)"}' | head -10

clean:
	@find . -name "*.pyc" -delete 2>/dev/null || true
