"""Receipt to OCEL evidence projection."""
def event(r):return {"activity":"sa2a.outcome","subject":r.subject,"effect_id":r.effect_id,"generation":r.generation,"provider":r.provider,"replay_key":r.replay_key,"outcome":r.outcome,"authority":"none"}
