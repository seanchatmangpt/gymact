import unittest
from dataclasses import replace
from datetime import datetime,timedelta,timezone
from gymact.explore_intent_frontier.context import SelectionContext
from gymact.explore_intent_frontier.frontier import resolve
from gymact.explore_intent_frontier.intent import SelectionIntent
from gymact.explore_intent_frontier.subject import Subject
class TestFrontier(unittest.TestCase):
    def test_divergent_latest_intents_refuse(self):
        t=datetime(2026,8,22,tzinfo=timezone.utc); a=SelectionContext(Subject("a/b","1"*40),"cut","2"*64,1,"MIN_SKEW","3"*64)
        b=replace(a,policy_digest="4"*64)
        x=SelectionIntent(a,"nonce-0001",t,t+timedelta(hours=1)); y=SelectionIntent(b,"nonce-0002",t,t+timedelta(hours=1))
        with self.assertRaisesRegex(ValueError,"REFUSED_DIVERGENT_INTENT_FRONTIER"): resolve((x,y),t)
if __name__=="__main__": unittest.main()
