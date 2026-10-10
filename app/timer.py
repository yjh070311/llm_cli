"""
计时工具模块，提供@timer装饰器，统计函数执行耗时
"""

import time
from functools import wraps
from  typing import Any,Callable,TypeVar

F=TypeVar("F",bound=Callable[...,Any])

def timer(func:F) ->F:
    """
    计时装饰器
    【计时】函数名（参数）
    """
    if _is_async(func):
        @wraps(func)
        async def async_wrapper(*args:Any,**kwargs:Any)->Any:
            start=time.perf_counter()
            result=await func(*args,**kwargs)
            elapsed=time.perf_counter()-start
            print(f"计时{func.__name__}耗时{elapsed:2f}秒")
            return result

        return async_wrapper 

def _is_async(func:Callable[...,Any])->bool:
    """
    判断函数是否为异步函数
    """

    import inspect
    return inspect.iscoroutinefunction(func)
