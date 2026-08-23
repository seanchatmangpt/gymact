from dataclasses import dataclass
import hashlib,json
@dataclass(frozen=True)
class Receipt:
    subject:str; selector:str; mode:str; standing:str; actuation_performed:bool=False
    def body(self)->dict[str,object]:return {'schema':'gymact.explore-composition-selector-calibration/1','subject':self.subject,'selector':self.selector,'mode':self.mode,'standing':self.standing,'actuation_performed':self.actuation_performed}
    def digest(self)->str:return hashlib.sha256(json.dumps(self.body(),sort_keys=True,separators=(',',':')).encode()).hexdigest()
