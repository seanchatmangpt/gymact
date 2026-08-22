from .admission import admit
from .census import census
from .strategy import Strategy,complete
from .storage import select_store
from .receipt import make_receipt
from .authority import require
def qualify(subject,epoch,witnesses,consumers,strategy:Strategy,*,durable=False,transactional=False):
    require("CONSTRUCT")
    admitted=admit(epoch,witnesses)
    states=census(consumers,admitted)
    ok=complete(strategy,states)
    store=select_store(durable=durable,transactional=transactional)
    standing="PARTIAL_ALIVE" if ok else "UNKNOWN"
    payload={"subject":subject.identity,"generation":epoch.generation,"event_id":epoch.event_id,
             "strategy":strategy.name,"states":states,"store":store.name,"standing":standing}
    return {"complete":ok,"standing":standing,"store":store.name,"receipt":make_receipt(payload)}
