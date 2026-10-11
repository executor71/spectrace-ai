"""Closed model; keys are existing identifiers, labels are never caller-supplied."""
LABELS=('Requirement','BusinessRule','Api','TestCase','Evidence','Execution')
RELATIONS={
    'SUPPORTED_BY':('Requirement','BusinessRule'), 'AFFECTS':('Requirement','Api'),
    'GENERATES':('Requirement','TestCase'), 'IMPLEMENTED_BY':('BusinessRule','Api'),
    'VERIFIED_BY':None, 'BASED_ON':('TestCase','Evidence'), 'EXECUTED_AS':('TestCase','Execution')}
# Existing Phase 7 IDs, matched only to canonical Phase 2 specification routes.
APIS={'POST /loans/{loanId}/approve':'API-LOAN-APPROVE','GET /assets/{assetId}':'API-ASSET-001'}
def key(node):return (node['type'],node['id'])
