"""Contracts for how cycle_compare surfaces abandoned region passes."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cycle_compare as cc


class AbandonmentNoticeTests(unittest.TestCase):
    def test_clean_region_has_no_notice(self):
        resp = {"region": 1, "hits": 4, "abandoned": 0, "in_region": 0}
        self.assertEqual(cc.abandonment_notices("native", resp), [])

    def test_abandoned_passes_are_reported_with_both_causes(self):
        resp = {"region": 1, "hits": 3, "abandoned": 5,
                "abandoned_reentry": 2, "abandoned_overrun": 3, "in_region": 0}
        text = " ".join(cc.abandonment_notices("beetle", resp))
        self.assertIn("beetle", text)
        self.assertIn("5 abandoned", text)
        self.assertIn("2 re-entry", text)
        self.assertIn("3 overrun", text)

    def test_pass_still_open_at_dump_time_is_reported(self):
        resp = {"region": 1, "hits": 0, "abandoned": 0, "in_region": 1}
        self.assertTrue(any("still open" in n for n in cc.abandonment_notices("native", resp)))

    def test_single_anchor_mode_has_no_notice(self):
        self.assertEqual(cc.abandonment_notices("native", {"region": 0, "hits": 4}), [])

    def test_backend_without_abandonment_fields_is_flagged(self):
        notices = cc.abandonment_notices("beetle", {"region": 1, "hits": 4})
        self.assertTrue(any("does not report" in n for n in notices))


if __name__ == "__main__":
    unittest.main()
