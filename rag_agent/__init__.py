"""rag_agent: ShopInspect 缺陷处置 RAG + Agent 模块。

通过 app/main.py 加一行 `app.include_router(router, prefix="/agent")` 接入,
单进程单端口,同进程 `import app.db` 读检测记录。配置独立(读 .env)。
"""
__version__ = "0.1.0"
