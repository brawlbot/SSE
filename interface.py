import asyncio
from client import ClientSSE

async def health_check():
    client = ClientSSE()
    await client.health_check(interval=0.5, max_checks=5)
    await client.close()


async def execute_script_k8s():
    client = ClientSSE()
    # command = "for i in {1..10}; do echo 'Log entry $i'; sleep 1; done"
    command = "ls /tmp"
    namespace = "dbext-resources"
    prefix = "sh6itcgl"
    await client.execute_script(command, namespace, prefix)
    await client.close()


if __name__ == "__main__":
    asyncio.run(execute_script_k8s())