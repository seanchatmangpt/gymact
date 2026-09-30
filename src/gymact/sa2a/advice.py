"""SELECT-only advice projection."""
def consume(e):return {"kind":"advice","effect_id":e.candidate.effect_id,"replay_key":e.candidate.replay_key,"authority":"none"}
