def frontier(scores:dict[str,tuple[float,...]])->tuple[str,...]:
    ids=sorted(scores); out=[]
    for i in ids:
        a=scores[i]; dominated=False
        for j in ids:
            if i==j: continue
            b=scores[j]
            if all(x>=y for x,y in zip(b,a)) and any(x>y for x,y in zip(b,a)):
                dominated=True; break
        if not dominated: out.append(i)
    return tuple(out)
