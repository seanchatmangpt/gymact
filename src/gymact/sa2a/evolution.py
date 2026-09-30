"""Powerless evolution candidate projection."""
def consume(e):return {"kind":"evolution_candidate","subject":e.candidate.subject,"generation":e.candidate.generation,"effect_id":e.candidate.effect_id,"replay_key":e.candidate.replay_key,"authority":"none"}
