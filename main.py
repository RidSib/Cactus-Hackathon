
import sys
sys.path.insert(0, "cactus/python/src")
functiongemma_path = "cactus/weights/functiongemma-270m-it"

import json, os, time
from cactus import cactus_init, cactus_complete, cactus_destroy
from google import genai
from google.genai import types


def generate_cactus(messages, tools):
    """Run function calling on-device via FunctionGemma + Cactus."""
    model = cactus_init(functiongemma_path)

    cactus_tools = [{
        "type": "function",
        "function": t,
    } for t in tools]

    raw_str = cactus_complete(
        model,
        [{"role": "system",
          "content": "You are a helpful assistant "
          "that can use tools."}] + messages,
        tools=cactus_tools,
        force_tools=True,
        max_tokens=256,
        stop_sequences=["<|im_end|>", "<end_of_turn>"],
    )

    cactus_destroy(model)

    try:
        raw = json.loads(raw_str)
    except json.JSONDecodeError:
        return {
            "function_calls": [],
            "total_time_ms": 0,
            "confidence": 0,
        }

    return {
        "function_calls": raw.get("function_calls", []),
        "total_time_ms": raw.get("total_time_ms", 0),
        "confidence": raw.get("confidence", 0),
    }


def generate_cloud(messages, tools):
    """Run function calling via Gemini Cloud API."""
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

    gemini_tools = [
        types.Tool(function_declarations=[
            types.FunctionDeclaration(
                name=t["name"],
                description=t["description"],
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        k: types.Schema(type=v["type"].upper(), description=v.get("description", ""))
                        for k, v in t["parameters"]["properties"].items()
                    },
                    required=t["parameters"].get("required", []),
                ),
            )
            for t in tools
        ])
    ]

    contents = [m["content"] for m in messages if m["role"] == "user"]

    start_time = time.time()

    # Try the newest Flash model first, then fall back to stable if needed.
    model_candidates = ["gemini-3-flash-preview", "gemini-2.5-flash"]
    last_error = None
    gemini_response = None

    for model_name in model_candidates:
        try:
            gemini_response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=types.GenerateContentConfig(tools=gemini_tools),
            )
            break
        except Exception as exc:
            last_error = exc

    if gemini_response is None:
        raise last_error

    total_time_ms = (time.time() - start_time) * 1000

    function_calls = []
    for candidate in gemini_response.candidates:
        for part in candidate.content.parts:
            if part.function_call:
                function_calls.append({
                    "name": part.function_call.name,
                    "arguments": dict(part.function_call.args),
                })

    return {
        "function_calls": function_calls,
        "total_time_ms": total_time_ms,
    }


def generate_hybrid(messages, tools, confidence_threshold=0.99):
    """Baseline hybrid inference strategy; fall back to cloud if Cactus Confidence is below threshold."""
    local = generate_cactus(messages, tools)

    if local["confidence"] >= confidence_threshold:
        local["source"] = "on-device"
        return local

    cloud = generate_cloud(messages, tools)
    cloud["source"] = "cloud (fallback)"
    cloud["local_confidence"] = local["confidence"]
    cloud["total_time_ms"] += local["total_time_ms"]
    return cloud


def print_result(label, result):
    """Pretty-print a generation result."""
    print(f"\n=== {label} ===\n")
    if "source" in result:
        print(f"Source: {result['source']}")
    if "confidence" in result:
        print(f"Confidence: {result['confidence']:.4f}")
    if "local_confidence" in result:
        print(f"Local confidence (below threshold): {result['local_confidence']:.4f}")
    print(f"Total time: {result['total_time_ms']:.2f}ms")
    for call in result["function_calls"]:
        print(f"Function: {call['name']}")
        print(f"Arguments: {json.dumps(call['arguments'], indent=2)}")


############## Tool definitions ##############

TOOLS = [
    {
        "name": "lookup_company_data",
        "description":
            "Look up data about a company such as "
            "revenue, payments, contracts, or costs",
        "parameters": {
            "type": "object",
            "properties": {
                "company": {
                    "type": "string",
                    "description": "Company name",
                },
                "metric": {
                    "type": "string",
                    "description":
                        "What to look up: revenue, "
                        "profit, cost, payments, "
                        "or contract",
                },
                "period": {
                    "type": "string",
                    "description":
                        "Time period like 2025, Q3, "
                        "or last quarter",
                },
            },
            "required": ["company"],
        },
    },
    {
        "name": "lookup_person",
        "description":
            "Look up information about a person "
            "such as salary, role, or contact details",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description":
                        "Person's full name",
                },
                "info_type": {
                    "type": "string",
                    "description":
                        "What to look up: salary, "
                        "role, department, or contact",
                },
            },
            "required": ["name"],
        },
    },
    {
        "name": "general_query",
        "description":
            "Handle a general question that does "
            "not involve a specific company or person",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description":
                        "The user's question",
                },
            },
            "required": ["query"],
        },
    },
]

############## Example usage ##############

if __name__ == "__main__":
    test_queries = [
        "Give me our revenue from Nvidia for 2025",
        "What is John Smith's salary?",
        "Show me the contract with Microsoft Azure",
        "How much did we pay Amazon last quarter?",
        "What role does Maria Garcia have?",
        "Pull up costs for Tesla in Q3",
        "What is the weather today?",
        "Who is our contact at Google?",
        "Compare payments to Apple vs Samsung",
    ]

    for query in test_queries:
        msgs = [{"role": "user", "content": query}]
        result = generate_cactus(msgs, TOOLS)
        fc = result.get("function_calls", [])
        conf = result.get("confidence", 0)
        t = result.get("total_time_ms", 0)
        if fc:
            c = fc[0]
            args = json.dumps(
                c["arguments"], ensure_ascii=False
            )
            print(
                f"[{conf:.3f}] {query}\n"
                f"      -> {c['name']}({args})"
            )
        else:
            print(
                f"[{conf:.3f}] {query}\n"
                f"      -> MISS"
            )
