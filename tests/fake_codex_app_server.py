"""Deterministic stdio peer for controller integration tests. No model/network calls."""
import argparse
import json
import sys

parser = argparse.ArgumentParser()
parser.add_argument("--trace", required=True)
parser.add_argument("--scenario", default="normal")
args = parser.parse_args()
task_count = 0
thread_id = "thr_test"


def send(message):
    print(json.dumps(message), flush=True)


def event(method, **params):
    send({"method": method, "params": {"threadId": thread_id, **params}})


def record(message):
    with open(args.trace, "a") as output:
        output.write(json.dumps(message) + "\n")


def request_user(method, params):
    send({"id": "server-1", "method": method, "params": {"threadId": thread_id, **params}})
    response = json.loads(sys.stdin.readline())
    record(response)
    assert response["id"] == "server-1", response
    return response["result"]


for line in sys.stdin:
    message = json.loads(line)
    record(message)
    method = message.get("method")
    reply = lambda result: send({"id": message["id"], "result": result})
    if method == "initialize":
        reply({"userAgent": "fake-codex", "platformOs": "linux"})
    elif method == "initialized":
        pass
    elif method in ("thread/start", "thread/resume"):
        assert not any(k in message["params"] for k in
                       ("approvalPolicy", "sandbox", "baseInstructions", "developerInstructions"))
        reply({"thread": {"id": thread_id, "status": {"type": "idle"}}, "model": "fake-model"})
    elif method == "account/rateLimits/read":
        if args.scenario == "reject_limits":
            send({"id": message["id"], "error": {"code": -32601, "message": "Unsupported method"}})
        else:
            reply({"rateLimits": {"secondary": {"usedPercent": 35, "windowDurationMins": 10080,
                                                "resetsAt": 1800000000}}})
    elif method == "thread/compact/start":
        if args.scenario == "disconnect_compact":
            sys.exit(0)
        if args.scenario == "reject_compact":
            send({"id": message["id"], "error": {"code": -32601, "message": "Unsupported method"}})
            continue
        turn = {"id": "compact-1", "status": "completed"}
        event("turn/started", turn={"id": turn["id"], "status": "inProgress"})
        event("item/started", turnId=turn["id"], item={"id": "c1", "type": "contextCompaction"})
        event("item/completed", turnId=turn["id"], item={"id": "c1", "type": "contextCompaction"})
        if args.scenario == "fail_compact":
            turn["status"] = "failed"
        event("turn/completed", turn=turn)
        # Events may precede the request acknowledgement.
        reply({})
    elif method == "turn/start":
        task_count += 1
        turn_id = f"turn-{task_count}"
        if args.scenario == "disconnect":
            sys.exit(0)
        assert message["params"]["threadId"] == thread_id
        assert len(message["params"]["input"]) in (2, 3)
        if len(message["params"]["input"]) == 3:
            assert message["params"]["input"][2]["text"].startswith("[Local experiment handoff:")
        event("turn/started", turn={"id": turn_id, "status": "inProgress"})
        ack_sent = args.scenario in ("stages", "late_steer")
        if ack_sent:
            reply({"turn": {"id": turn_id, "status": "inProgress"}})
            for amount in ([50, 70, 90] if args.scenario == "stages" else [50]):
                for _ in range(2):
                    event("thread/tokenUsage/updated", turnId=turn_id,
                          tokenUsage={"last": {"totalTokens": amount}, "modelContextWindow": 100})
                steer = json.loads(sys.stdin.readline())
                record(steer)
                assert steer["method"] == "turn/steer", steer
                assert steer["params"]["expectedTurnId"] == turn_id
                if args.scenario == "late_steer":
                    send({"id": steer["id"], "error": {"code": -32602, "message": "Turn already completed"}})
                else:
                    send({"id": steer["id"], "result": {"turnId": turn_id}})
        if args.scenario == "tool_activity":
            file_change = {"id": "file1", "type": "fileChange", "status": "inProgress", "changes": []}
            mcp_call = {"id": "mcp1", "type": "mcpToolCall", "status": "inProgress",
                        "server": "docs", "tool": "search", "arguments": {"query": "example"}}
            event("item/started", turnId=turn_id, item=file_change)
            event("item/started", turnId=turn_id, item=mcp_call)
            file_change["changes"] = [{"path": "example.py", "kind": {"type": "update"}, "diff": "patch"}]
            event("item/fileChange/patchUpdated", turnId=turn_id, itemId="file1", changes=file_change["changes"])
            event("item/mcpToolCall/progress", turnId=turn_id, itemId="mcp1", message="Reading documentation")
            result = request_user("item/fileChange/requestApproval", {"turnId": turn_id, "itemId": "file1"})
            assert result["decision"] == "accept"
            event("item/completed", turnId=turn_id, item={**file_change, "status": "completed"})
            event("item/completed", turnId=turn_id, item={**mcp_call, "status": "completed"})
        if args.scenario == "command_activity":
            command = {"id": "cmd1", "type": "commandExecution", "command": "echo test",
                       "cwd": "/work/project", "status": "inProgress", "commandActions": []}
            event("item/started", turnId=turn_id, item=command)
        if args.scenario in ("approval", "command_activity"):
            result = request_user("item/commandExecution/requestApproval",
                                  {"turnId": turn_id, "itemId": "cmd1", "command": "echo test",
                                   "reason": "test approval", "availableDecisions": ["accept", "decline"]})
            assert result["decision"] == ("accept" if args.scenario == "command_activity" else "decline")
        if args.scenario == "command_activity":
            event("item/commandExecution/outputDelta", turnId=turn_id, itemId="cmd1", delta="test\n")
            event("item/completed", turnId=turn_id,
                  item={**command, "status": "completed", "exitCode": 0, "aggregatedOutput": "test\n"})
        text = "Task done."
        if args.scenario == "terminal_ui":
            command = {"id": "cmd-ui", "type": "commandExecution", "command": "cat synthetic.txt",
                       "cwd": "/synthetic", "status": "inProgress"}
            event("item/started", turnId=turn_id, item=command)
            event("item/completed", turnId=turn_id, item={**command, "status": "completed", "exitCode": 0,
                  "aggregatedOutput": "\n".join(f"logical line {n}" for n in range(1, 13))})
            text = "# Terminal smoke\n\n| Name | Value |\n|---|---|\n| synthetic | 12 |\n\n```python\nprint('hello')\n```\n\n**Complete.**"
        item = {"type": "agentMessage", "id": "answer", "phase": "final_answer", "text": text}
        event("item/started", turnId=turn_id, item=item)
        event("item/agentMessage/delta", itemId="answer", turnId=turn_id, delta=text)
        event("item/completed", turnId=turn_id, item=item)
        amount = 70 if args.scenario == "medium" else 30 if args.scenario == "low" else 90
        last = {"inputTokens": amount - 5, "outputTokens": 5, "totalTokens": amount,
                "cachedInputTokens": 60, "reasoningOutputTokens": 0}
        event("thread/tokenUsage/updated", turnId=turn_id,
              tokenUsage={"last": last, "total": {"totalTokens": 9999999}, "modelContextWindow": 100})
        if args.scenario == "native":
            event("item/completed", turnId=turn_id, item={"id": "native1", "type": "contextCompaction"})
        if args.scenario == "pending":
            event("item/started", turnId=turn_id, item={"id": "pending1", "type": "commandExecution"})
        event("turn/completed", turn={"id": turn_id,
                                     "status": "failed" if args.scenario == "failed_task" else "completed"})
        if not ack_sent:
            reply({"turn": {"id": turn_id, "status": "inProgress"}})
    else:
        send({"id": message.get("id"), "error": {"code": -32601, "message": "Unexpected method"}})
