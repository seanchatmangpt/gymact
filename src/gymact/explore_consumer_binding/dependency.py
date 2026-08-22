def propagate(standing_by_repo:dict[str,str],deps:dict[str,set[str]])->dict[str,str]:
    out=dict(standing_by_repo); changed=True
    while changed:
        changed=False
        for repo,parents in deps.items():
            if any(out.get(p) in {'BUILD_BROKEN','BLOCKED'} for p in parents) and out.get(repo)!='BLOCKED':
                out[repo]='BLOCKED'; changed=True
    return out
