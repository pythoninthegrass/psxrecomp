"""Contracts for the anchored two-port devtrace comparison, over invented event streams."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import devtrace_anchor as da
import devtrace_diff as dd

VBLANK, CDROM, SIO0 = 0, 2, 7


def ev(seq, cycle, src, detail=0):
    return {"seq": seq, "cycle": cycle, "frame": 0, "srcn": src, "detail": detail}


def stream(rows, first_seq=0):
    return [ev(first_seq + i, c, s, d) for i, (c, s, d) in enumerate(rows)]


class FindAnchorTests(unittest.TestCase):
    def test_first_event_of_source_is_the_anchor(self):
        events = stream([(10, VBLANK, 0), (20, SIO0, 0), (30, SIO0, 0)])
        self.assertEqual(da.find_anchor(events, SIO0, 0), 1)

    def test_ordinal_selects_nth_event_of_source(self):
        events = stream([(10, SIO0, 0), (20, VBLANK, 0), (30, SIO0, 0)])
        self.assertEqual(da.find_anchor(events, SIO0, 1), 2)

    def test_missing_source_raises_not_found(self):
        events = stream([(10, VBLANK, 0)])
        with self.assertRaises(da.AnchorNotFound):
            da.find_anchor(events, SIO0, 0)

    def test_wrapped_ring_raises_aged_out_instead_of_anchoring_later(self):
        events = stream([(10, VBLANK, 0), (20, SIO0, 0)], first_seq=5000)
        with self.assertRaises(da.AnchorAgedOut):
            da.find_anchor(events, SIO0, 0)


def fake_port(events, page_cap, total=None):
    """query() stand-in: filters by cyc_lo, drops newest beyond page_cap like the server."""
    total = len(events) + events[0]["seq"] if total is None else total

    def query(port, cmd, **kw):
        lo = int(kw.get("cyc_lo", 0))
        rows = [e for e in events if e["cycle"] >= lo][:page_cap]
        return {"ok": True, "total": total, "events": rows}
    return query


class PullAllTests(unittest.TestCase):
    def test_pages_past_the_server_truncation(self):
        events = stream([(i * 10, VBLANK, 0) for i in range(25)])
        got = da.pull_all(1, query=fake_port(events, page_cap=10))
        self.assertEqual([e["seq"] for e in got["events"]], list(range(25)))

    def test_gap_between_pages_is_reported_as_aged_out(self):
        events = stream([(i * 10, VBLANK, 0) for i in range(25)])
        del events[12:15]
        with self.assertRaises(da.AnchorAgedOut):
            da.pull_all(1, query=fake_port(events, page_cap=10, total=25))

    def test_unreachable_tail_is_reported_not_returned_short(self):
        events = stream([(i * 10, VBLANK, 0) for i in range(5)])
        with self.assertRaises(da.PullIncomplete):
            da.pull_all(1, query=fake_port(events, page_cap=10, total=9))


class ReportTests(unittest.TestCase):
    def test_drift_is_relative_to_each_sides_own_anchor(self):
        native = stream([(1000, SIO0, 0), (1100, VBLANK, 0), (1200, VBLANK, 0), (1400, SIO0, 0)])
        beetle = stream([(5000, SIO0, 0), (5100, VBLANK, 0), (5250, VBLANK, 0), (5400, SIO0, 0)])
        rows = {r["name"]: r for r in da.report(native, beetle, SIO0, 0, drift=100)}
        self.assertEqual(rows["vblank"]["max_drift"], 50)
        self.assertIsNone(rows["vblank"]["first_ordinal"])

    def test_first_ordinal_over_threshold_and_counts(self):
        native = stream([(0, SIO0, 0), (100, VBLANK, 0), (200, VBLANK, 0), (300, VBLANK, 0), (1000, SIO0, 0)])
        beetle = stream([(0, SIO0, 0), (100, VBLANK, 0), (500, VBLANK, 0), (900, VBLANK, 0), (1000, SIO0, 0)])
        rows = {r["name"]: r for r in da.report(native, beetle, SIO0, 0, drift=250)}
        vb = rows["vblank"]
        self.assertEqual((vb["n_count"], vb["b_count"]), (3, 3))
        self.assertEqual(vb["first_ordinal"], 1)
        self.assertEqual(vb["first_delta"], 300)
        self.assertEqual(vb["max_drift"], 600)

    def test_events_past_common_span_are_excluded(self):
        native = stream([(0, SIO0, 0), (100, VBLANK, 0), (10_000, VBLANK, 0)])
        beetle = stream([(0, SIO0, 0), (100, VBLANK, 0)])
        rows = {r["name"]: r for r in da.report(native, beetle, SIO0, 0, drift=1)}
        self.assertEqual(rows["vblank"]["n_count"], 1)

    def test_max_span_caps_the_compared_window(self):
        native = stream([(0, SIO0, 0), (100, VBLANK, 0), (200, VBLANK, 0), (300, SIO0, 0)])
        beetle = stream([(0, SIO0, 0), (100, VBLANK, 0), (200, VBLANK, 0), (300, SIO0, 0)])
        rows = {r["name"]: r for r in da.report(native, beetle, SIO0, 0, 1, max_span=150)}
        self.assertEqual(rows["vblank"]["n_count"], 1)

    def test_known_divergence_label_is_kept(self):
        native = stream([(0, SIO0, 0), (100, CDROM, 0)])
        beetle = stream([(0, SIO0, 0), (900, CDROM, 0)])
        rows = {r["name"]: r for r in da.report(native, beetle, SIO0, 0, drift=10)}
        self.assertEqual(rows["cdrom"]["known"], dd.KNOWN_DIVERGENCES["cdrom"])


class AlignTests(unittest.TestCase):
    def test_extra_event_cost_is_separated_from_timing_drift(self):
        # beetle has one extra CDROM event (detail 9) costing 1000 cycles; the
        # matched events otherwise drift by 5 each step; drift = beetle - native.
        native = stream([(0, SIO0, 0), (100, CDROM, 1), (200, CDROM, 2), (300, CDROM, 3)])
        beetle = stream([(0, SIO0, 0), (105, CDROM, 1), (1105, CDROM, 9), (1205, CDROM, 2), (1310, CDROM, 3)])
        res = da.align(native, beetle, SIO0, 0)
        self.assertEqual(res["extra_native"], 0)
        self.assertEqual(res["extra_beetle"], 1)
        self.assertEqual(res["extra_cost"], 1000)
        self.assertEqual(res["timing_cost"], 10)
        self.assertEqual(res["extra_cost"] + res["timing_cost"], res["total_offset"])

    def test_identical_shapes_have_no_extras(self):
        native = stream([(0, SIO0, 0), (100, CDROM, 1), (200, CDROM, 2)])
        beetle = stream([(0, SIO0, 0), (150, CDROM, 1), (260, CDROM, 2)])
        res = da.align(native, beetle, SIO0, 0)
        self.assertEqual((res["extra_native"], res["extra_beetle"], res["extra_cost"]), (0, 0, 0))
        self.assertEqual(res["timing_cost"], 60)


if __name__ == "__main__":
    unittest.main()
