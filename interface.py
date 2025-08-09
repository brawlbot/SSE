import asyncio
from client import ClientSSE

async def health_check():
    client = ClientSSE()
    await client.health_check(interval=0.5, max_checks=5)
    await client.close()


async def execute_script_k8s():
    client = ClientSSE()
    command = "seq 1 10 | xargs -I {} sh -c 'echo \"Log entry {}\"; sleep 0.5'"
    # command = "sleep 1 && ls /tmp"
    namespace = "dbext-resources"
    prefix = "sh6itcgl"
    await client.execute_script(command, namespace, prefix)
    await client.close()


if __name__ == "__main__":
    asyncio.run(execute_script_k8s())