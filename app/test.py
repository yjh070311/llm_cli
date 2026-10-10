import httpx
import asyncio
import time

start_time=time.time()

#处理单个函数
async def get_poke(client,url):
    resp=await client.get(url)
    pokemon=resp.json()

    return pokemon['name']

async def main():
    #创建client
    async with httpx.AsyncClient() as client:

        tasks=[]
        for number in range(1,151):
            #循环赋值url
            url=f'https://pokeapi.co/api/v2/pokemon/{number}'

            #coroutine(协程)可以暂停和恢复的函数，执行到await暂停，结果回来再继续
            tasks.append(asyncio.ensure_future(get_poke(client,url)))

        #同时执行多个协程，全部完成，把结果汇总成一个列表
        original=await asyncio.gather(*tasks)
        for pokemon in original:
            print(pokemon)

asyncio.run(main())

print(time.time()-start_time)

