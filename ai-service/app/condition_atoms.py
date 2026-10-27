"""Source-quoted approval guard; no policy, expected-result or graph writes.

Only explicit actor grants and self-approval prohibition are recognized.
Other domains retain uncertain model proposals and require human review.
"""
import re

def atoms(text):
    result={}
    for clause in re.split(r'[.\n]+|(?<=으며)\s*',text):
        clause=clause.strip()
        if not clause:continue
        if re.search(r'승인(?:할 수 있|한다)',clause) and not re.search(r'승인[^.]{0,20}(?:수 없|않|금지)',clause):
            for role in ('부서장','자산관리 담당자'):
                if role in clause:result['approval.actor.'+role]=dict(quote=clause,role=role)
        lifted=re.search(r'금지[^.]{0,12}(?:해제|폐지|삭제|없애)|(?:본인|자기)[^.]{0,40}승인[^.]{0,20}허용한다',clause)
        if not lifted and re.search(r'(?:본인|자기)[^.]{0,40}승인[^.]{0,25}(?:수 없다|금지|허용하지)',clause):
            result['approval.self.denied']=dict(quote=clause,role=None)
    return result

def reconcile(request,changes):
    conditions=request['baselineSnapshot']['analysis'].get('confirmedConditions',[])
    before={};recognized=0
    for condition in conditions:
        values=atoms(condition['text'])
        if values:recognized+=1
        for key,value in values.items():before[key]=dict(value,source=condition)
    after=atoms(request['proposalContent'])
    contradiction=any(c['changeType']=='REMOVED' and any(key in after and value['source']['text']==c.get('baselineCondition',c.get('beforeCondition')) for key,value in before.items()) for c in changes)
    if not conditions or recognized!=len(conditions) or not contradiction:return changes
    output=[]
    for key in sorted(set(before)|set(after)):
        old=before.get(key);new=after.get(key)
        kind='UNCHANGED' if old and new else 'ADDED' if new else 'UNCERTAIN'
        output.append(dict(changeId='C'+str(len(output)+1),conditionKey=key,beforeCondition=old['quote'] if old else None,baselineCondition=old['source']['text'] if old else None,afterCondition=new['quote'] if new else None,changeType=kind,rationale='명시된 승인 주체/자기 승인 금지의 원문 조건을 대조하여 모델의 삭제 모순을 검토 후보로 조정했습니다.',evidenceChunkIds=[old['source']['chunkId']] if old else [],requiresConfirmation=True,certainty='SOURCE_RULE_ATOM' if old and new else 'SEMANTIC_PROPOSAL' if new else 'UNCERTAIN',businessPolicyApproved=False,reconciliation='SOURCE_QUOTED_APPROVAL_GUARD'))
    return output
