import unittest
from build import ROOT, render
from inventory import CAPACITY, LANES, POLICIES, PORTS, PROFILES, STOCK, demand, feasible_moves, replay, serve


class InventoryTests(unittest.TestCase):
    def test_conservation_capacity_and_weekly_balance(self):
        for profile in PROFILES:
            for seed in range(1, 11):
                for policy in POLICIES:
                    previous = None
                    for row in replay(demand(seed, profile), policy):
                        if previous:
                            self.assertEqual(row["opening"], {p: previous["dock"][p] +
                                             previous["in_transit"][p] for p in PORTS})
                        self.assertEqual(sum(row["dock"].values()) + sum(row["in_transit"].values()), STOCK)
                        self.assertLessEqual(row["empty"], CAPACITY)
                        self.assertGreaterEqual(min(row["dock"].values()), 0)
                        for p in PORTS:
                            self.assertEqual(row["requested"][p], row["shipped"][p] + row["shortfall"][p])
                        previous = row
                    self.assertEqual(previous["empty"], 0)

    def test_proportional_service(self):
        stock = dict.fromkeys(PORTS, 0)
        stock["Atlas"] = 10
        requests = dict.fromkeys(LANES, 0)
        requests["Atlas", "Beacon"] = 9
        requests["Atlas", "Cove"] = 21
        loaded = serve(stock, requests)
        self.assertEqual((loaded["Atlas", "Beacon"], loaded["Atlas", "Cove"]), (3, 7))

    def test_future_requests_do_not_influence_dispatch(self):
        a = demand(17, "surge")
        b = a[:4] + [{lane: 1000 for lane in LANES} for _ in a[4:]]
        self.assertEqual(replay(a, "forecast")[:4], replay(b, "forecast")[:4])

    def test_cannot_move_empty_containers_still_in_transit(self):
        moves = feasible_moves({"Atlas": 60, "Beacon": 20, "Cove": 0},
                               dict.fromkeys(PORTS, 25), {"Atlas": 3, "Beacon": 0, "Cove": 0})
        self.assertEqual(moves, [("Atlas", "Cove", 3)])

    def test_committed_report_reproduces(self):
        self.assertEqual((ROOT / "index.html").read_text(encoding="utf-8"), render())
