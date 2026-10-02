UUID = {"type": "string", "format": "uuid", "pattern": "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"}

def strict(properties, required):
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}

INPUTS = {
    "search_knowledge": strict({"query": {"type": "string", "minLength": 1, "maxLength": 2000, "pattern": "\\S"},
        "topK": {"type": "integer", "minimum": 1, "maximum": 5, "default": 5},
        "strategy": {"type": "string", "enum": ["VECTOR", "HYBRID"], "default": "VECTOR"}}, ["query"])
}
for name in ("analyze_requirement", "get_test_cases", "get_evaluation_result"):
    INPUTS[name] = strict({"requirementId": UUID}, ["requirementId"])
INPUTS["execute_approved_test"] = strict({"testCaseId": UUID}, ["testCaseId"])
