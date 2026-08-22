def compare(left, right, path:str="$")->tuple[str,...]:
    if type(left) is not type(right): return (path,)
    if isinstance(left,dict):
        diffs=[]
        for k in sorted(set(left)|set(right)): diffs.extend(compare(left.get(k),right.get(k),f"{path}.{k}"))
        return tuple(diffs)
    if isinstance(left,(list,tuple)):
        diffs=[]
        for i in range(max(len(left),len(right))):
            a=left[i] if i<len(left) else object(); b=right[i] if i<len(right) else object()
            diffs.extend(compare(a,b,f"{path}[{i}]"))
        return tuple(diffs)
    return () if left==right else (path,)
