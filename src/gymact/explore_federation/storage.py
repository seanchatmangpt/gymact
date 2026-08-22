import json
class MemoryStore:
    def __init__(self): self.rows=[]
    def append(self,row:dict): self.rows.append(dict(row))
    def replay(self): return tuple(dict(x) for x in self.rows)

def encode_jsonl(rows:list[dict])->str:
    return "".join(json.dumps(r,sort_keys=True,separators=(",",":"))+"\n" for r in rows)
