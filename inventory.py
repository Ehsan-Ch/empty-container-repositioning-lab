"""Weekly container inventory replay on a synthetic three-port network."""
from random import Random
from statistics import mean

PORTS = ("Atlas", "Beacon", "Cove")
LANES = tuple((origin, destination) for origin in PORTS for destination in PORTS
              if origin != destination)
PROFILES = {
    "balanced": (16, 16, 16, 16, 16, 16),
    "imbalanced": (23, 22, 10, 18, 10, 17),
    "surge": (21, 19, 12, 18, 12, 17),
}
POLICIES = ("none", "reactive", "forecast")
STOCK = 150
CAPACITY = 24
WEEKS = 18
RUNS = 80


def demand(seed, profile):
    rng = Random(seed)
    base = PROFILES[profile]
    return [
        {lane: max(0, level + rng.randint(-6, 6)
                   + (13 if profile == "surge" and 7 <= week <= 11 and lane[0] == "Atlas" else 0))
         for lane, level in zip(LANES, base)}
        for week in range(1, WEEKS + 1)
    ]


def rebalance(projected, target, capacity):
    """Move surplus empties to the largest deficits, with stable port tie-breaking."""
    available = dict(projected)
    moves = []
    while capacity:
        source = max(PORTS, key=lambda port: available[port] - target[port])
        destination = max(PORTS, key=lambda port: target[port] - available[port])
        amount = min(available[source] - target[source],
                     target[destination] - available[destination], capacity)
        if amount <= 0:
            break
        available[source] -= amount
        available[destination] += amount
        capacity -= amount
        moves.append((source, destination, amount))
    return moves


def serve(stock, requests):
    """Share scarce stock proportionally across the two destinations."""
    outbound = {}
    for port in PORTS:
        lanes = [lane for lane in LANES if lane[0] == port]
        requested = sum(requests[lane] for lane in lanes)
        total = min(stock[port], requested)
        if not total:
            outbound.update(dict.fromkeys(lanes, 0))
            continue
        quotas = {lane: divmod(requests[lane] * total, requested) for lane in lanes}
        for lane in lanes:
            outbound[lane] = quotas[lane][0]
        allocated = sum(outbound[lane] for lane in lanes)
        for lane in sorted(lanes, key=lambda lane: (-quotas[lane][1], lane))[:total-allocated]:
            outbound[lane] += 1
    return outbound


def replay(requests_by_week, policy):
    if policy not in POLICIES:
        raise ValueError("Unknown policy")
    stock = dict.fromkeys(PORTS, STOCK // len(PORTS))
    incoming = dict.fromkeys(PORTS, 0)
    history = []
    timeline = []
    for week, requests in enumerate(requests_by_week, 1):
        opening = {port: stock[port] + incoming[port] for port in PORTS}
        loaded = serve(opening, requests)
        requested = {p: sum(v for (o, _), v in requests.items() if o == p) for p in PORTS}
        shipped = {p: sum(v for (o, _), v in loaded.items() if o == p) for p in PORTS}
        stock = {p: opening[p] - shipped[p] for p in PORTS}
        incoming = {p: sum(q for (_, d), q in loaded.items() if d == p) for p in PORTS}
        history.append(requested)
        moves = []
        if policy != "none" and week < len(requests_by_week):
            projected = {p: stock[p] + incoming[p] for p in PORTS}
            target = dict.fromkeys(PORTS, 22)
            if policy == "forecast":
                target = {p: round(mean(r[p] for r in history[-3:])) + 5 for p in PORTS}
            # A surplus can be moved only from current dock stock, not from cargo still sailing.
            moves = feasible_moves(projected, target, stock)
            for source, destination, amount in moves:
                stock[source] -= amount
                incoming[destination] += amount
        timeline.append({
            "week": week, "opening": opening, "requested": requested, "shipped": shipped,
            "shortfall": {p: requested[p] - shipped[p] for p in PORTS},
            "dock": stock.copy(), "in_transit": incoming.copy(),
            "moves": moves, "empty": sum(move[2] for move in moves),
        })
    return timeline


def feasible_moves(projected, target, stock):
    # Raise the source floor when some of its projected inventory is still in transit.
    # Deficits still use the true target.
    supply = {p: max(0, min(stock[p], projected[p] - target[p])) for p in PORTS}
    need = {p: max(0, target[p] - projected[p]) for p in PORTS}
    # Separate balances represent transferable surplus and unmet targets on a single scale.
    net = {p: supply[p] - need[p] for p in PORTS}
    return rebalance(net, dict.fromkeys(PORTS, 0), CAPACITY)


def tally(rows):
    return {"requested": sum(sum(w["requested"].values()) for w in rows),
            "missed": sum(sum(w["shortfall"].values()) for w in rows),
            "empty": sum(w["empty"] for w in rows)}


def experiment():
    report = {}
    for profile in PROFILES:
        scores = {p: [] for p in POLICIES}
        example = {}
        for seed in range(1, RUNS + 1):
            requests = demand(seed, profile)
            for policy in POLICIES:
                rows = replay(requests, policy)
                scores[policy].append(tally(rows))
                if seed == 1:
                    example[policy] = rows
        summary = {}
        for policy in POLICIES:
            results = scores[policy]
            baseline = scores["none"]
            recovered = sum(b["missed"] - r["missed"] for b, r in zip(baseline, results))
            moves = sum(r["empty"] for r in results)
            summary[policy] = {
                "missed": round(mean(r["missed"] for r in results), 3),
                "empty": round(mean(r["empty"] for r in results), 3),
                "fill": round(1 - sum(r["missed"] for r in results) /
                              sum(r["requested"] for r in results), 6),
                "recovered_per_move": round(recovered / moves, 4) if moves else None,
                "better": sum(r["missed"] < b["missed"] for r, b in zip(results, baseline)),
                "worse": sum(r["missed"] > b["missed"] for r, b in zip(results, baseline)),
            }
        report[profile] = {"summary": summary, "example": example}
    return {"runs": RUNS, "weeks": WEEKS, "ports": PORTS, "profiles": report}
