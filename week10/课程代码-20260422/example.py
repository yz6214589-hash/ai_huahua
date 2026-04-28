from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

class S(TypedDict, total=False):
    n: int
    log: list

def double(s): return {"n": s["n"]*2, "log": s.get("log",[])+["x2"]}
def add_one(s): return {"n": s["n"]+1, "log": s.get("log",[])+["+1"]}
def route(s): return "add_one" if s["n"]<100 else END

g = StateGraph(S)
g.add_node("double", double)
g.add_node("add_one", add_one)
g.add_edge(START, "double")
g.add_conditional_edges("double", route)
g.add_edge("add_one", "double") # 形成循环: 翻倍 -> 加一 -> 翻倍 ..

graph = g.compile(checkpointer=MemorySaver())
result = graph.invoke({"n":3}, config={"configurable":{"thread_id":"demo"}})
print(result)