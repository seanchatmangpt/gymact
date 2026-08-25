#!/usr/bin/env python3
import copy, hashlib, json, pathlib, re, subprocess, sys
ROOT=pathlib.Path(__file__).resolve().parents[2]
HERE=pathlib.Path(__file__).resolve().parent
SUBJECT=json.loads((HERE/'subject.json').read_text())
HEX40=re.compile(r'^[0-9a-f]{40}$')

def classify(s):
    if s.get('consumer_repo')!='seanchatmangpt/gymact': return 'REFUSED[FOREIGN_CONSUMER]'
    if s.get('producer_repo')!='seanchatmangpt/ggen-marketplace': return 'REFUSED[FOREIGN_PRODUCER]'
    if s.get('producer_pack')!='epistemic-sensor-factory-pack': return 'REFUSED[FOREIGN_PACK]'
    if not HEX40.fullmatch(s.get('consumer_base','')): return 'REFUSED[MALFORMED_CONSUMER_BASE]'
    if not HEX40.fullmatch(s.get('producer_head','')): return 'REFUSED[MALFORMED_PRODUCER_HEAD]'
    if s.get('consequential_do') is not False: return 'REFUSED[DO_FORBIDDEN]'
    authority=s.get('authority','').split('|')
    if 'VERIFY' not in authority or 'DO' in authority: return 'REFUSED[AUTHORITY_FENCE]'
    if not s.get('evidence_root'): return 'REFUSED[MISSING_EVIDENCE_ROOT]'
    if s.get('standing')!='ADMITTED': return 'REFUSED[SUBJECT_NOT_ADMITTED]'
    return 'ALIVE'

def mutate(base, case):
    s=copy.deepcopy(base)
    for key,value in case.get('set',{}).items(): s[key]=value
    for key in case.get('delete',[]): s.pop(key,None)
    return s

def main():
    failures=[]
    cases=sorted((HERE/'cases').glob('*.json'))
    if len(cases)<20:
        print(f'REFUSED[INSUFFICIENT_CASES]={len(cases)}'); return 1
    ids=set()
    for path in cases:
        case=json.loads(path.read_text()); cid=case['id']
        if cid in ids: failures.append(f'duplicate:{cid}')
        ids.add(cid)
        actual=classify(mutate(SUBJECT,case)); expected=case['expected']
        print(f'{cid}={actual}')
        if actual!=expected: failures.append(f'{cid}:{actual}!={expected}')
    exact_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    digest=hashlib.sha256(json.dumps(SUBJECT,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    print('EXACT_HEAD='+exact_head); print('SUBJECT_DIGEST='+digest); print('CASE_COUNT='+str(len(cases)))
    if failures:
        print('REFUSED[R54_COURT]='+','.join(failures)); return 1
    print('R54_EPISTEMIC_CONSUMER=ALIVE'); return 0

if __name__=='__main__': sys.exit(main())
