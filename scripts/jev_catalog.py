"""Repository catalog validation and deterministic, advisory source selection."""
import json
from pathlib import Path
import re

from jev_workers import bounded_map

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CATALOG = Path(__file__).resolve().parents[1] / "catalog.json"


def strings(value):
    return isinstance(value, list) and all(isinstance(x, str) and x.strip() for x in value)


def load_catalog(path=DEFAULT_CATALOG):
    with Path(path).open(encoding="utf-8") as stream:
        raw = stream.read(131073)
    if len(raw) > 131072:
        raise ValueError("catalog exceeds 128 KiB")
    catalog = json.loads(raw)
    if (not isinstance(catalog, dict) or type(catalog.get("schema_version")) is not int
            or catalog["schema_version"] != 1):
        raise ValueError("catalog schema_version must be 1")
    workflows, documents = catalog.get("workflows"), catalog.get("documents")
    if not isinstance(workflows, dict) or not isinstance(documents, dict) or not 1 <= len(documents) <= 64:
        raise ValueError("catalog needs workflows and 1–64 documents")
    for key, workflow in workflows.items():
        if (not isinstance(workflow, dict) or not strings(workflow.get("keywords"))
                or not strings(workflow.get("validation"))):
            raise ValueError(f"invalid workflow {key}")
    paths = set()
    for key, doc in documents.items():
        if not re.fullmatch(r"[a-z][a-z0-9_]*", key) or not isinstance(doc, dict):
            raise ValueError("invalid document ID or record")
        for field in ("path", "description", "owns", "status"):
            if not isinstance(doc.get(field), str) or not doc[field].strip():
                raise ValueError(f"{key}: missing {field}")
        path = Path(doc["path"])
        if path.is_absolute() or ".." in path.parts or doc["path"] in paths:
            raise ValueError(f"{key}: path must be unique and repository-relative")
        paths.add(doc["path"])
        if doc["status"] not in {"instructions", "current", "mixed", "historical"}:
            raise ValueError(f"{key}: invalid authority status")
        for field in ("workflows", "keywords", "sections", "requires", "superseded_by"):
            if not strings(doc.get(field)):
                raise ValueError(f"{key}: invalid {field}")
        if set(doc["workflows"]) - set(workflows):
            raise ValueError(f"{key}: unknown workflow")
        if (set(doc["requires"]) | set(doc["superseded_by"])) - set(documents):
            raise ValueError(f"{key}: unknown companion document")
        for field in ("always", "entrypoint"):
            if type(doc.get(field, False)) is not bool:
                raise ValueError(f"{key}: {field} must be boolean")
    return catalog


def mentions(text, term):
    # Sentence-final punctuation is allowed; extensions such as .md.bak are not.
    return re.search(r"(?<![\w.-])" + re.escape(term.casefold()) + r"(?![\w-]|\.[\w])", text.casefold()) is not None


def pinned_documents(prompt, required, catalog):
    """Pin full paths or unambiguous basenames (README.md / SKILL.md are ambiguous)."""
    documents = catalog["documents"]
    if set(required) - set(documents):
        raise ValueError("unknown required document ID")
    names = [Path(doc["path"]).name for doc in documents.values()]
    pinned = set(required)
    for key, doc in documents.items():
        name = Path(doc["path"]).name
        if mentions(prompt, doc["path"]) or (names.count(name) == 1 and mentions(prompt, name)):
            pinned.add(key)
    return pinned


def local_plan(task, required, catalog):
    documents = catalog["documents"]
    pinned = pinned_documents(task, required, catalog)
    workflows = {key for key, item in catalog["workflows"].items()
                 if any(mentions(task, term) for term in item["keywords"])}
    for key in pinned:
        workflows.update(documents[key]["workflows"])
    actions, reasons = {}, {}
    for key, doc in documents.items():
        relevant = bool(workflows.intersection(doc["workflows"]))
        if key in pinned or doc.get("always"):
            actions[key], reasons[key] = "read", "explicit source" if key in pinned else "repository instruction"
        elif relevant and (doc.get("entrypoint") or any(mentions(task, term) for term in doc["keywords"])):
            actions[key], reasons[key] = "read", "local workflow/section match"
        elif relevant or not workflows or not doc["workflows"]:
            actions[key], reasons[key] = "inspect", "uncertain relevance; search headings locally"
        else:
            actions[key], reasons[key] = "skip", "outside locally matched workflows; advisory only"
    return actions, reasons, pinned, workflows


def reconcile(actions, reasons, catalog):
    """Required companions and current authorities cannot be skipped by the classifier."""
    changed = True
    while changed:
        changed = False
        for key, doc in catalog["documents"].items():
            if actions[key] != "read":
                continue
            for companion in doc["requires"] + doc["superseded_by"]:
                if actions[companion] != "read":
                    actions[companion] = "read"
                    reasons[companion] = f"required/current authority companion of {key}"
                    changed = True


def _available(job):
    root, path = job
    resolved = (Path(root) / path).resolve()
    if not resolved.is_relative_to(Path(root)):
        raise ValueError(f"catalog source escapes repository root: {path}")
    return resolved.is_file()


def availability(root, documents, workers=None):
    return bounded_map(_available, [(str(Path(root).resolve()), doc["path"]) for doc in documents.values()], workers)


def validation_guidance(workflows, catalog):
    return {key: catalog["workflows"][key]["validation"] for key in catalog["workflows"] if key in workflows}
