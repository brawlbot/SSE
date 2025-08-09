import asyncio
from client import ClientSSE

async def health_check():
    client = ClientSSE()
    await client.health_check(interval=0.5, max_checks=5)
    await client.close()


async def execute_script_k8s():
    client = ClientSSE()
    command = "for i in 1 2 3 4 5 6 7 8 9 10; do printf \"Log entry %s\\n\" $i; sleep 0.5; done"
    # command = "sleep 1 && ls /tmp"
    namespace = "dbext-resources"
    prefix = "sh6itcgl"
    await client.execute_script(command, namespace, prefix)
    await client.close()


async def execute_script_k8s_invalid():
    client = ClientSSE()
    invalid_command = "ls /wrong/path"
    # command = "sleep 1 && ls /tmp"
    namespace = "dbext-resources"
    prefix = "sh6itcgl"
    await client.execute_script(invalid_command, namespace, prefix)
    await client.close()

if __name__ == "__main__":
    asyncio.run(health_check())
    asyncio.run(execute_script_k8s())
    asyncio.run(execute_script_k8s_invalid())