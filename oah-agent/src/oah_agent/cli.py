"""Command line for the OAH One Health assistant.

    oah-ask "where does nitrate exceed safe levels in Coimbra?"
    oah-ask --chat                           # multi-turn session; follow-ups keep context
    oah-ask --brief                          # risk briefing for the whole dataset
    oah-ask --brief --site site-c1-mondego
    oah-ask --facts --site site-c1-mondego   # computed facts only, no model call

Every answer is followed by a grounding verdict: a deterministic check that each
figure in the answer appears in the data the tools actually returned. `--facts`
makes no model call at all, which is both the offline fallback and the way to
see exactly what a narrative is built on.
"""

from __future__ import annotations

import argparse
import json
import sys

from dotenv import load_dotenv

load_dotenv()

from .briefing import dataset_briefing, narrate, site_briefing  # noqa: E402
from .grounding import check, format_verdict  # noqa: E402


def _report(result: dict) -> None:
    print(result["answer"], flush=True)

    verdict = result.get("grounding")
    if verdict:
        print(f"\n[{format_verdict(verdict)}]", file=sys.stderr)

    trace = result.get("trace") or []
    urls = [step["fhir_url"] for step in trace if step.get("fhir_url")]
    if urls:
        print("\nSource queries:", file=sys.stderr)
        for url in dict.fromkeys(urls):
            print(f"  {url}", file=sys.stderr)


def _chat(model, verbose) -> None:
    from .assistant import Conversation

    conversation = Conversation(model=model)
    print("OAH One Health assistant. Ask a question, or Ctrl-D to leave.\n")
    while True:
        try:
            question = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not question:
            continue
        if question in {"exit", "quit"}:
            return
        try:
            _report(conversation.ask(question, verbose=verbose))
        except Exception as exc:
            print(f"error: {exc}", file=sys.stderr)
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("question", nargs="*", help="natural-language question about the OAH dataset")
    parser.add_argument("--chat", action="store_true", help="multi-turn session; follow-ups keep context")
    parser.add_argument("--brief", action="store_true", help="produce a One Health risk briefing")
    parser.add_argument("--facts", action="store_true", help="print computed facts as JSON; makes no model call")
    parser.add_argument("--site", help="restrict a briefing to one site id")
    parser.add_argument("--tag", default="oah-demo", help="dataset tag to query (default: oah-demo)")
    parser.add_argument("--model", help="override the model (default: $OPENAI_MODEL or gpt-4o)")
    parser.add_argument("--verbose", action="store_true", help="show tool calls as they happen")
    args = parser.parse_args()

    if args.chat:
        _chat(args.model, args.verbose)
        return

    if args.brief or args.facts:
        facts = site_briefing(args.site, dataset_tag=args.tag) if args.site else dataset_briefing(dataset_tag=args.tag)
        if args.facts:
            print(json.dumps(facts, indent=2, default=str))
            return

        narrative = narrate(facts, model=args.model)
        print(narrative, flush=True)
        # The briefing's figures are derived in Python, so the same grounding
        # check applies: the narrative must not introduce numbers of its own.
        print(f"\n[{format_verdict(check(narrative, [facts]))}]", file=sys.stderr)

        urls = facts.get("fhir_urls") or [u for b in facts.get("briefings", []) for u in b.get("fhir_urls", [])]
        if urls:
            print("\nSource queries:", file=sys.stderr)
            for url in dict.fromkeys(urls):
                print(f"  {url}", file=sys.stderr)
        return

    if not args.question:
        parser.error("give a question, or use --chat / --brief / --facts")

    from .assistant import ask

    _report(ask(" ".join(args.question), model=args.model, verbose=args.verbose))


if __name__ == "__main__":
    main()
