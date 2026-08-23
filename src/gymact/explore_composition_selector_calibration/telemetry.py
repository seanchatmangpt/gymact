from dataclasses import asdict,dataclass
from .calibration import Calibration
from .qualification import Qualification
@dataclass(frozen=True)
class Telemetry:
    selector:str; mode:str; support:int; coverage:str; mean_width:str; standing:str
def project(selector:str,calibration:Calibration,qualification:Qualification)->Telemetry:
    return Telemetry(selector,calibration.mode.value,calibration.support,str(calibration.coverage),str(calibration.mean_width),qualification.standing.value)
