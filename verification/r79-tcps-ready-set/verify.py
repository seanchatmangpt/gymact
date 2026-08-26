#!/usr/bin/env python3
import hashlib, json, pathlib, re, sys
HERE = pathlib.Path(__file__).resolve().parent
SUBJECT = json.loads((HERE / "subject.json").read_text())
HEX40 = re.compile(r"^[0-9a-f]{40}$")

def classify(s):
    if s.get("consumer_repo") != "seanchatmangpt/gymact": return "REFUSED[FOREIGN_CONSUMER]"
    if s.get("producer_repo") != "seanchatmangpt/ggen-marketplace": return "REFUSED[FOREIGN_PRODUCER]"
    if s.get("producer_pack") != "portfolio-epistemic-observability-pack": return "REFUSED[FOREIGN_PACK]"
    if s.get("producer_capability") != "R78_TCPS_READY_SET_CAPITAL": return "REFUSED[FOREIGN_CAPABILITY]"
    if not HEX40.fullmatch(s.get("consumer_base", "")): return "REFUSED[MALFORMED_CONSUMER_BASE]"
    if not HEX40.fullmatch(s.get("producer_head", "")): return "REFUSED[MALFORMED_PRODUCER_HEAD]"
    if s.get("prior_consumer_standing") != "MERGED_ALIVE": return "REFUSED[PRIOR_STANDING]"
    if s.get("allocation_law") != "legality-before-priority": return "REFUSED[ALLOCATION_LAW]"
    authority = set(s.get("authority", "").split("|"))
    if "VERIFY" not in authority or "DO" in authority: return "REFUSED[AUTHORITY_FENCE]"
    if s.get("consequential_do") is not False: return "REFUSED[DO_FORBIDDEN]"
    if s.get("standing") != "ADMITTED": return "REFUSED[SUBJECT_NOT_ADMITTED]"
    return "ALIVE"

def main():
    standing = classify(SUBJECT)
    digest = hashlib.sha256(json.dumps(SUBJECT, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    print("R79_CONSUMER=" + standing)
    print("SUBJECT_DIGEST=" + digest)
    return 0 if standing == "ALIVE" else 1

if __name__ == "__main__": sys.exit(main())
