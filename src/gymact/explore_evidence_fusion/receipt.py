from dataclasses import dataclass
import hashlib,json
@dataclass(frozen=True)
class Receipt:
    schema:str; subject:str; strategy:str; standing:str; clusters:int; diversity:str; store:str; actuation_performed:bool; digest:str
def issue(subject,strategy,standing,clusters,diversity,store):
    body={"schema":"gymact.explore-evidence-fusion/1","subject":subject.identity,"strategy":strategy.value,"standing":standing,"clusters":clusters,"diversity":str(diversity),"store":store.name,"actuation_performed":False}
    digest=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    return Receipt(**body,digest=digest)
def replay(r):
    if r.actuation_performed: return False
    body={k:getattr(r,k) for k in ("schema","subject","strategy","standing","clusters","diversity","store","actuation_performed")}
    return hashlib.sha256(json.dumps(body,sort_keys=True,separators=(",",":")).encode()).hexdigest()==r.digest
