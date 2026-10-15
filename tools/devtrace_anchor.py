#!/usr/bin/env python3
"""devtrace_anchor.py — anchored two-port DEVICE-EVENT comparison.

devtrace_diff.py compares the ports over an absolute guest-cycle window, which
only means something when both sit at the same guest point. They do not: the two
BIOS boots differ in length (KNOWN CD-controller version difference), so each
side is anchored independently at a named event (source + ordinal; default the
first SIO0 event) and every event is compared by per-source ordinal using
cycles RELATIVE to that side's own anchor.

Sign convention: drift = beetle_rel - native_rel. Positive means Beetle's Nth
event fires later than native's (native is fast).

Ring: 1M events (device_trace.c), seq is monotonic since boot. devtrace_dump
truncates each response at ~157k events (12 MB buffer), dropping the newest, so
pull_all pages with cyc_lo up to the first pull's total and checks seq
contiguity. Anchor and every comparison come from that one snapshot. If the
ring has wrapped (oldest seq is not 0) the Nth event of a source in the window
is not the Nth since boot, so the anchor is reported as aged out instead of
being silently placed on a later event. See tools/DEVTRACE_ANCHOR.md.

Usage:
  python tools/devtrace_anchor.py [--native PORT] [--beetle PORT]
        [--anchor-source sio0] [--anchor-ordinal 0]
        [--span N]           # cap common post-anchor span in cycles
        [--drift N]          # first ordinal whose |drift| > N (default 2_000_000)
        [--align SRC ...]    # also run sequence alignment over (source,detail)
        [--strict]           # do not label KNOWN_DIVERGENCES
"""
import argparse
import difflib
import sys

import devtrace_diff as dd

NAME_TO_SRC = {v: k for k, v in dd.SRC.items()}


class AnchorError(Exception):
    pass


class AnchorNotFound(AnchorError):
    pass


class AnchorAgedOut(AnchorError):
    pass


class PullIncomplete(AnchorError):
    pass


def pull_all(port, query=dd.query):
    """Snapshot of the ring as of the first pull, seq-contiguous, oldest first.

    devtrace_dump returns at most ~157k events per response (12 MB buffer) and
    drops the NEWEST ones silently, so a single pull of a long run is truncated.
    Later pages are fetched with cyc_lo and merged by seq; the snapshot ends at
    the first pull's total. A seq gap means the ring wrapped mid-pull.
    """
    first = query(port, "devtrace_dump", count=1 << 20)
    if not first.get("ok"):
        raise PullIncomplete(f"[port {port}] devtrace_dump failed: {first}")
    target = first["total"]
    by_seq = {e["seq"]: e for e in first["events"]}
    page = first
    for _ in range(64):
        if not page["events"] or max(by_seq) + 1 >= target:
            break
        page = query(port, "devtrace_dump", count=1 << 20,
                     cyc_lo=str(page["events"][-1]["cycle"]))
        if not page.get("ok"):
            raise PullIncomplete(f"[port {port}] devtrace_dump failed: {page}")
        if page["events"][-1]["seq"] <= max(by_seq):
            break
        by_seq.update((e["seq"], e) for e in page["events"])
    events = [by_seq[k] for k in sorted(by_seq) if k < target]
    for a, b in zip(events, events[1:]):
        if b["seq"] != a["seq"] + 1:
            raise AnchorAgedOut(
                f"[port {port}] ring wrapped during the pull (seq gap {a['seq']}->{b['seq']})")
    if events and events[-1]["seq"] + 1 < target:
        raise PullIncomplete(
            f"[port {port}] pull stopped at seq {events[-1]['seq']} of {target}")
    return {"total": target, "events": events}


def find_anchor(events, source, ordinal=0):
    """Index into events of the ordinal-th event of source; raises if untrustworthy."""
    if events and events[0]["seq"] > 0:
        raise AnchorAgedOut(
            f"ring wrapped: oldest retained seq={events[0]['seq']} (cycle "
            f"{events[0]['cycle']}), so ordinal {ordinal} of "
            f"{dd.SRC.get(source, source)} in this window is not the ordinal "
            f"since boot")
    seen = 0
    for i, e in enumerate(events):
        if e["srcn"] == source:
            if seen == ordinal:
                return i
            seen += 1
    raise AnchorNotFound(
        f"no event #{ordinal} of source {dd.SRC.get(source, source)} in the ring")


def _post_anchor(events, source, ordinal):
    idx = find_anchor(events, source, ordinal)
    base = events[idx]["cycle"]
    return [dict(e, rel=e["cycle"] - base) for e in events[idx:]]


def _common(native, beetle, source, ordinal, max_span=None):
    n = _post_anchor(native, source, ordinal)
    b = _post_anchor(beetle, source, ordinal)
    span = min(n[-1]["rel"], b[-1]["rel"])
    if max_span is not None:
        span = min(span, max_span)
    return ([e for e in n if e["rel"] <= span],
            [e for e in b if e["rel"] <= span], span)


def report(native, beetle, source, ordinal, drift, strict=False, max_span=None):
    n, b, _ = _common(native, beetle, source, ordinal, max_span)
    ns, bs = dd.by_source(n), dd.by_source(b)
    rows = []
    for s in sorted(set(ns) | set(bs)):
        ne, be = ns.get(s, []), bs.get(s, [])
        name = dd.SRC.get(s, f"src{s}")
        first = None
        max_abs = 0
        max_drift = 0
        for i in range(min(len(ne), len(be))):
            d = be[i]["rel"] - ne[i]["rel"]
            if abs(d) > abs(max_drift):
                max_drift = d
            if first is None and abs(d) > drift:
                first = (i, d)
        rows.append({
            "name": name, "n_count": len(ne), "b_count": len(be),
            "first_ordinal": first[0] if first else None,
            "first_delta": first[1] if first else None,
            "max_drift": max_drift,
            "known": None if strict else dd.KNOWN_DIVERGENCES.get(name),
        })
    return rows


def align(native, beetle, source, ordinal, only_sources=None):
    """Align the post-anchor streams over (source, detail); split offset change."""
    n = _post_anchor(native, source, ordinal)
    b = _post_anchor(beetle, source, ordinal)
    if only_sources is not None:
        n = [e for e in n if e["srcn"] in only_sources]
        b = [e for e in b if e["srcn"] in only_sources]
    key = lambda e: (e["srcn"], e["detail"])
    sm = difflib.SequenceMatcher(None, [key(e) for e in n], [key(e) for e in b],
                                 autojunk=False)
    extra_n = extra_b = 0
    extra_cost = timing_cost = 0
    prev_off = 0
    prev_was_equal = False
    ops = sm.get_opcodes()
    # a trailing unmatched run is one port simply having run longer, not extras
    if ops and ops[-1][0] != "equal":
        ops = ops[:-1]
    for tag, i1, i2, j1, j2 in ops:
        if tag == "equal":
            for k in range(i2 - i1):
                off = b[j1 + k]["rel"] - n[i1 + k]["rel"]
                if k == 0 and not prev_was_equal:
                    extra_cost += off - prev_off
                else:
                    timing_cost += off - prev_off
                prev_off = off
            prev_was_equal = True
        else:
            extra_n += i2 - i1
            extra_b += j2 - j1
            prev_was_equal = False
    return {"ratio": sm.ratio(), "extra_native": extra_n, "extra_beetle": extra_b,
            "extra_cost": extra_cost, "timing_cost": timing_cost,
            "total_offset": prev_off}


def _parse_source(text):
    return int(text) if text.isdigit() else NAME_TO_SRC[text]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--native", type=int, default=4370)
    ap.add_argument("--beetle", type=int, default=4380)
    ap.add_argument("--anchor-source", default="sio0")
    ap.add_argument("--anchor-ordinal", type=int, default=0)
    ap.add_argument("--drift", type=int, default=2_000_000)
    ap.add_argument("--align", nargs="*", default=None, metavar="SRC")
    ap.add_argument("--span", type=int, default=None,
                    help="cap the common post-anchor span (cycles) for reproducible figures")
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    src = _parse_source(args.anchor_source)
    try:
        nat = pull_all(args.native)
        bet = pull_all(args.beetle)
    except AnchorError as e:
        print(f"PULL ERROR: {e}", file=sys.stderr)
        sys.exit(3)
    ne, be = nat["events"], bet["events"]
    print(f"native(:{args.native}): {len(ne)} events (total={nat['total']})")
    print(f"beetle(:{args.beetle}): {len(be)} events (total={bet['total']})")
    try:
        for label, ev in (("native", ne), ("beetle", be)):
            i = find_anchor(ev, src, args.anchor_ordinal)
            print(f"{label} anchor {args.anchor_source}#{args.anchor_ordinal}: cycle {ev[i]['cycle']}")
    except AnchorError as e:
        print(f"ANCHOR ERROR ({label}): {e}", file=sys.stderr)
        sys.exit(3)

    n, b, span = _common(ne, be, src, args.anchor_ordinal, args.span)
    print(f"common post-anchor span: {span} cycles\n")
    print(f"{'source':<8} {'n cnt':>8} {'b cnt':>8}  {'first >drift':<24} {'max |drift|':>14}")
    known = {}
    for r in report(ne, be, src, args.anchor_ordinal, args.drift, args.strict, args.span):
        first = "none" if r["first_ordinal"] is None else f"#{r['first_ordinal']} {r['first_delta']:+,d}"
        tag = "  (KNOWN)" if r["known"] and r["first_ordinal"] is not None else ""
        if r["known"]:
            known[r["name"]] = r["known"]
        print(f"{r['name']:<8} {r['n_count']:>8} {r['b_count']:>8}  {first:<24} {r['max_drift']:>+14,d}{tag}")
    for nm, why in known.items():
        print(f"  KNOWN {nm}: {why}")

    if args.align is not None:
        only = {_parse_source(s) for s in args.align} or None
        a = align(ne, be, src, args.anchor_ordinal, only)
        print(f"\nalignment over (source,detail), ratio {a['ratio']:.3f}: "
              f"extra native={a['extra_native']} extra beetle={a['extra_beetle']}\n"
              f"  cycles from extra events: {a['extra_cost']:+,d}\n"
              f"  cycles from timing drift: {a['timing_cost']:+,d}\n"
              f"  total offset (beetle-native) at last match: {a['total_offset']:+,d}")


if __name__ == "__main__":
    main()
